import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats as stats_scipy
from statsmodels.stats.outliers_influence import variance_inflation_factor


df = pd.read_csv("../data/raw/nba_full_data.csv")



st.title("NBA Analytics Dashboard")

st.header("League Overview")

stats = st.selectbox("Select Stats", df.select_dtypes(include=[np.number]).columns.to_list())

if stats not in df.select_dtypes(include=[np.number]).columns:
    stats = "ppg"  # default stat

st.plotly_chart(px.histogram(df, x=stats, nbins=30,marginal="box", title=stats.upper() + " Distribution"))
st.plotly_chart(px.box(df, x='positions', y=stats, title=stats.upper() + " by Position"))
st.plotly_chart(px.scatter(df, x='salary', y=stats, color='positions', title="Salary vs " + stats.upper()))

st.header("Correlation Analysis")

col1, col2 = st.columns(2)

with col1:
    stat1 = st.selectbox("Select First Stat", df.select_dtypes(include=[np.number]).columns.to_list(), key="stat1")

with col2:
    stat2 = st.selectbox("Select Second Stat", df.select_dtypes(include=[np.number]).columns.to_list(), key="stat2", index=1)

# Calculate correlation
correlation = df[[stat1, stat2]].corr().iloc[0, 1]

st.metric("Correlation Coefficient", f"{correlation:.3f}")

# Scatter plot with trendline
fig = px.scatter(df, x=stat1, y=stat2, color='positions', 
                 title=f"{stat1.upper()} vs {stat2.upper()} (Correlation: {correlation:.3f})",
                 trendline="ols", trendline_scope="overall")
st.plotly_chart(fig)

st.header("Correlation Matrix")

# Calculate correlation matrix for numeric columns
numeric_cols = df.select_dtypes(include=[np.number]).columns.to_list()
corr_matrix = df[numeric_cols].corr()

# Create heatmap
fig_heatmap = px.imshow(corr_matrix, 
                        text_auto='.2f',
                        aspect="auto",
                        color_continuous_scale='RdBu_r',
                        zmin=-1, zmax=1,
                        title="Correlation Heatmap of All Numeric Stats")
fig_heatmap.update_layout(height=800)
st.plotly_chart(fig_heatmap, use_container_width=True)

# Show highly correlated pairs
st.subheader("Highly Correlated Stats (|correlation| > 0.7)")

# Get upper triangle of correlation matrix
mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
corr_pairs = corr_matrix.where(mask).stack().reset_index()
corr_pairs.columns = ['Stat 1', 'Stat 2', 'Correlation']

# Filter for high correlations
high_corr = corr_pairs[abs(corr_pairs['Correlation']) > 0.7].sort_values('Correlation', ascending=False, key=abs)

if len(high_corr) > 0:
    st.dataframe(high_corr.style.background_gradient(cmap='RdBu_r', subset=['Correlation'], vmin=-1, vmax=1), 
                 use_container_width=True)
else:
    st.info("No stat pairs found with |correlation| > 0.7")

st.header("Variance Inflation Factor (VIF) Analysis")

st.info("""
**VIF Interpretation:**
- VIF = 1: No multicollinearity
- VIF = 1-5: Moderate correlation (acceptable)
- VIF = 5-10: High multicollinearity (consider removing)
- VIF > 10: Severe multicollinearity (should remove)
""")

# Select features for VIF analysis
numeric_cols = df.select_dtypes(include=[np.number]).columns.to_list()

# Option to exclude certain columns
excluded_cols = st.multiselect("Exclude columns from VIF analysis", numeric_cols, default=["salary", "season"])
features_for_vif = [col for col in numeric_cols if col not in excluded_cols]

if len(features_for_vif) >= 2:
    # Clean data
    df_clean = df[features_for_vif].dropna()
    
    if len(df_clean) > 0:
        try:
            # Calculate VIF
            vif_data = pd.DataFrame()
            vif_data["Feature"] = features_for_vif
            vif_data["VIF"] = [variance_inflation_factor(df_clean.values, i) 
                               for i in range(len(features_for_vif))]
            
            # Sort by VIF
            vif_data = vif_data.sort_values('VIF', ascending=False)
            
            # Add severity level
            def get_severity(vif):
                if vif > 10:
                    return "🔴 Severe"
                elif vif > 5:
                    return "🟡 High"
                elif vif > 1:
                    return "🟢 Moderate"
                else:
                    return "🟢 None"
            
            vif_data["Severity"] = vif_data["VIF"].apply(get_severity)
            
            # Display table
            st.dataframe(vif_data, use_container_width=True)
            
            # Visualize VIF
            fig = px.bar(vif_data, x='Feature', y='VIF', 
                        title="VIF by Feature",
                        color='VIF',
                        color_continuous_scale='Reds')
            fig.add_hline(y=5, line_dash="dash", line_color="orange", 
                         annotation_text="Threshold: 5")
            fig.add_hline(y=10, line_dash="dash", line_color="red", 
                         annotation_text="Threshold: 10")
            st.plotly_chart(fig, use_container_width=True)
            
            # Show problematic features
            high_vif = vif_data[vif_data['VIF'] > 10]
            if len(high_vif) > 0:
                st.warning(f"⚠️ {len(high_vif)} features have VIF > 10 (severe multicollinearity)")
            
        except Exception as e:
            st.error(f"Error calculating VIF: {str(e)}")
    else:
        st.warning("No valid data after removing missing values")
else:
    st.warning("Need at least 2 numeric features for VIF analysis")

st.header("Outlier Detection & Analysis")

st.info("""
**Outlier Detection Methods:**
- **IQR Method:** Values below Q1 - 1.5×IQR or above Q3 + 1.5×IQR
- **Z-Score Method:** Values with |z-score| > 3
- **Isolation Forest:** ML-based anomaly detection
""")

# Select feature for outlier analysis
outlier_stat = st.selectbox("Select stat for outlier detection", 
                             df.select_dtypes(include=[np.number]).columns.to_list(),
                             key="outlier_stat")

# Method selection
method = st.radio("Detection Method", ["IQR Method", "Z-Score Method"], horizontal=True)

# Clean data
df_clean = df[[outlier_stat]].dropna()

if len(df_clean) > 0:
    
    # IQR Method
    def detect_outliers_iqr(data, column):
        Q1 = data[column].quantile(0.25)
        Q3 = data[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outliers = data[(data[column] < lower_bound) | (data[column] > upper_bound)]
        return outliers, lower_bound, upper_bound, Q1, Q3, IQR
    
    # Z-Score Method
    def detect_outliers_zscore(data, column, threshold=3):
        z_scores = stats_scipy.zscore(data[column])
        outliers = data[np.abs(z_scores) > threshold]
        return outliers, z_scores
    
    # Create columns for side-by-side display
    col1, col2, col3 = st.columns(3)
    
    # IQR Detection
    if method == "IQR Method":
        outliers_iqr, lower, upper, q1, q3, iqr = detect_outliers_iqr(df, outlier_stat)
        
        with col1:
            st.metric("Outliers (IQR)", len(outliers_iqr))
        with col2:
            st.metric("Lower Bound", f"{lower:.2f}")
        with col3:
            st.metric("Upper Bound", f"{upper:.2f}")
        
        # Box plot with outliers highlighted
        fig_box = go.Figure()
        fig_box.add_trace(go.Box(y=df[outlier_stat], name=outlier_stat,
                                 boxmean='sd', marker_color='lightblue'))
        fig_box.update_layout(title=f"Box Plot: {outlier_stat.upper()} (IQR Method)",
                             yaxis_title=outlier_stat)
        st.plotly_chart(fig_box, use_container_width=True)
        
        # Show outlier details
        if len(outliers_iqr) > 0:
            st.subheader("IQR Outliers")
            # Add all columns for context
            outlier_display = df.loc[outliers_iqr.index].copy()
            outlier_display['outlier_value'] = outlier_display[outlier_stat]
            st.dataframe(outlier_display.sort_values(outlier_stat, ascending=False), 
                        use_container_width=True)
    
    # Z-Score Detection
    if method == "Z-Score Method":
        outliers_z, z_scores = detect_outliers_zscore(df, outlier_stat)
        
        st.subheader("Z-Score Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Outliers (Z-Score > 3)", len(outliers_z))
        with col2:
            st.metric("Max Z-Score", f"{np.max(np.abs(z_scores)):.2f}")
        
        # Distribution with z-score overlay
        df_z = df.copy()
        df_z['z_score'] = z_scores
        df_z['is_outlier'] = np.abs(z_scores) > 3
        
        fig_dist = px.histogram(df_z, x=outlier_stat, color='is_outlier',
                               title=f"Distribution with Z-Score Outliers: {outlier_stat.upper()}",
                               labels={'is_outlier': 'Outlier'},
                               marginal="box")
        st.plotly_chart(fig_dist, use_container_width=True)
        
        # Z-score scatter
        df_z['index'] = range(len(df_z))
        fig_z = px.scatter(df_z, x='index', y='z_score', color='is_outlier',
                          title="Z-Scores Across All Players",
                          labels={'index': 'Player Index', 'z_score': 'Z-Score'})
        fig_z.add_hline(y=3, line_dash="dash", line_color="red", annotation_text="Threshold: +3")
        fig_z.add_hline(y=-3, line_dash="dash", line_color="red", annotation_text="Threshold: -3")
        st.plotly_chart(fig_z, use_container_width=True)
        
        if len(outliers_z) > 0:
            st.subheader("Z-Score Outliers")
            outlier_z_display = df.loc[outliers_z.index].copy()
            outlier_z_display['z_score'] = z_scores[outliers_z.index]
            st.dataframe(outlier_z_display.sort_values('z_score', ascending=False, key=abs), 
                        use_container_width=True)

st.header("Outlier Treatment Strategies")

treatment = st.selectbox("Select Treatment Method", 
                        ["None (Keep Outliers)", 
                         "Remove Outliers", 
                         "Winsorization (Cap at percentiles)",
                         "Log Transformation"])

if treatment == "Winsorization (Cap at percentiles)":
    lower_percentile = st.slider("Lower Percentile", 0, 25, 5)
    upper_percentile = st.slider("Upper Percentile", 75, 100, 95)
    
    lower_cap = df[outlier_stat].quantile(lower_percentile/100)
    upper_cap = df[outlier_stat].quantile(upper_percentile/100)
    
    df_treated = df.copy()
    df_treated[f'{outlier_stat}_treated'] = df[outlier_stat].clip(lower_cap, upper_cap)
    
    # Compare distributions
    fig_compare = go.Figure()
    fig_compare.add_trace(go.Histogram(x=df[outlier_stat], name='Original', opacity=0.7))
    fig_compare.add_trace(go.Histogram(x=df_treated[f'{outlier_stat}_treated'], 
                                       name='Winsorized', opacity=0.7))
    fig_compare.update_layout(title="Original vs Winsorized Distribution",
                             barmode='overlay')
    st.plotly_chart(fig_compare, use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Original Mean", f"{df[outlier_stat].mean():.2f}")
        st.metric("Original Std", f"{df[outlier_stat].std():.2f}")
    with col2:
        st.metric("Treated Mean", f"{df_treated[f'{outlier_stat}_treated'].mean():.2f}")
        st.metric("Treated Std", f"{df_treated[f'{outlier_stat}_treated'].std():.2f}")

elif treatment == "Log Transformation":
    # Handle negative values
    min_val = df[outlier_stat].min()
    if min_val <= 0:
        shift = abs(min_val) + 1
        st.info(f"Shifting data by {shift:.2f} to handle non-positive values")
        df_treated = df.copy()
        df_treated[f'{outlier_stat}_log'] = np.log(df[outlier_stat] + shift)
    else:
        df_treated = df.copy()
        df_treated[f'{outlier_stat}_log'] = np.log(df[outlier_stat])
    
    fig_log = go.Figure()
    fig_log.add_trace(go.Histogram(x=df[outlier_stat], name='Original', opacity=0.7))
    fig_log.add_trace(go.Histogram(x=df_treated[f'{outlier_stat}_log'], 
                                   name='Log Transformed', opacity=0.7))
    fig_log.update_layout(title="Original vs Log Transformed Distribution",
                         barmode='overlay')
    st.plotly_chart(fig_log, use_container_width=True)

# Multi-variate outlier detection
st.header("Multivariate Outlier Detection")

st.write("Detect players who are outliers across all statistics simultaneously")

# Select multiple features
selected_features = df.drop(columns=["season","age"]).select_dtypes(include=[np.number]).columns.to_list()
if len(selected_features) >= 2:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    
    # Prepare data
    df_multi = df[selected_features].dropna()
    
    if len(df_multi) > 0:
        # Standardize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(df_multi)
        
        # Contamination parameter (expected proportion of outliers)
        contamination = st.slider("Contamination (% of outliers expected)", 
                                 min_value=0.01, max_value=0.3, value=0.1, step=0.01)
        
        # Isolation Forest
        iso_forest = IsolationForest(contamination=contamination, random_state=42)
        outlier_labels = iso_forest.fit_predict(X_scaled)
        
        # -1 for outliers, 1 for inliers
        df_multi['is_outlier'] = outlier_labels == -1
        df_multi['anomaly_score'] = iso_forest.score_samples(X_scaled)
        
        n_outliers = df_multi['is_outlier'].sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Multivariate Outliers", n_outliers)
        with col2:
            st.metric("Percentage", f"{(n_outliers/len(df_multi)*100):.1f}%")
        
        # Visualize with first 2 features
        if len(selected_features) >= 2:
            fig_multi = px.scatter(df_multi, x=selected_features[0], y=selected_features[1],
                                  color='is_outlier',
                                  title=f"Multivariate Outliers: {selected_features[0]} vs {selected_features[1]}",
                                  labels={'is_outlier': 'Outlier'},
                                  hover_data=selected_features)
            st.plotly_chart(fig_multi, use_container_width=True)

# Outlier Treatment Options


st.header("Conclussion")
st.text("We need models that are robust to outliers and multicolinearity.")
st.subheader("1. Huber Regression (Most Robust to Outliers)")
st.text(" - Uses squared loss for small residuals, absolute loss for large residuals\n - Automatically downweights outliers\n - L2 regularization handles multicollinearity")
st.subheader("2. Ridge Regression (Handles Multicollinearity)")
st.text(" - L2 penalty shrinks correlated coefficients together\n - Never eliminates features (unlike Lasso)\n - Excellent for multicollinearity")
st.subheader("3. Random Forest (Naturally Robust)")
st.text(" - Median/mean of trees reduces outlier impact\n - Tree splits don't care about multicollinearity\n - Feature randomness handles correlated features\n - No assumptions about data distribution")
