import streamlit as st
# from analyzers.report_merger_agent import IntelligentReportMerger # RIMOSSO: Non più necessario importare l'agente qui
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from pathlib import Path # NUOVO: Importato per la gestione dei percorsi

# NUOVO: Percorso al file JSON dei dati della dashboard pre-generati
DASHBOARD_DATA_INPUT_PATH = Path(__file__).resolve().parent / "reports" / "final_dashboard_data.json"

# Page configuration with enhanced styling
st.set_page_config(
    layout="wide", 
    page_title="DAG Intelligence Dashboard",
    page_icon="🔬",
    initial_sidebar_state="expanded"
)

# Custom CSS for enhanced styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    
    .priority-critical {
        border-left-color: #dc2626 !important;
    }
    
    .priority-high {
        border-left-color: #ea580c !important;
    }
    
    .priority-medium {
        border-left-color: #ca8a04 !important;
    }
    
    .priority-low {
        border-left-color: #16a34a !important;
    }
    
    .dag-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #e5e7eb;
        transition: transform 0.2s;
        margin-bottom: 1rem;
    }
    
    .dag-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.15);
    }
    
    .health-excellent { color: #16a34a; }
    .health-good { color: #65a30d; }
    .health-warning { color: #ca8a04; }
    .health-critical { color: #dc2626; }
    
    .sidebar-section {
        background: #f8fafc;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner="Caricamento dati dashboard...") # Aggiunto spinner per un feedback visivo
def load_data():
    """
    Loads and returns the fully analyzed DAG data from a pre-generated JSON file.
    It no longer re-runs the analysis.
    """
    if not DASHBOARD_DATA_INPUT_PATH.exists():
        st.error(
            f"❌ Dati della dashboard non trovati! Assicurati di aver eseguito "
            f"`python -m analyzers.report_merger_agent` per generare il file: "
            f"`{DASHBOARD_DATA_INPUT_PATH.name}` nella cartella `reports/`."
        )
        st.stop() # Ferma l'esecuzione dell'app Streamlit
        return {} # Non dovrebbe essere raggiunto, ma buona pratica

    try:
        with open(DASHBOARD_DATA_INPUT_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        st.success(f"Dati della dashboard caricati con successo da {DASHBOARD_DATA_INPUT_PATH.name}!")
        return data
    except json.JSONDecodeError as e:
        st.error(f"❌ Errore nella lettura del file JSON dei dati della dashboard: {e}")
        st.info("Il file potrebbe essere corrotto. Prova a rigenerare i dati eseguendo `python -m analyzers.report_merger_agent`.")
        st.stop()
        return {}
    except Exception as e:
        st.error(f"❌ Errore imprevisto durante il caricamento dei dati: {e}")
        st.stop()
        return {}

def get_priority_config(priority):
    """Returns emoji, color, and CSS class for priority levels."""
    config = {
        "CRITICAL": {"emoji": "🚨", "color": "#dc2626", "class": "priority-critical"},
        "HIGH": {"emoji": "🔥", "color": "#ea580c", "class": "priority-high"},
        "MEDIUM": {"emoji": "⚠️", "color": "#ca8a04", "class": "priority-medium"},
        "LOW": {"emoji": "✅", "color": "#16a34a", "class": "priority-low"}
    }
    return config.get(priority, {"emoji": "❔", "color": "#6b7280", "class": ""})

def get_health_status(score):
    """Returns health status configuration based on score."""
    if score >= 90: return {"status": "Excellent", "color": "#16a34a", "class": "health-excellent"}
    if score >= 75: return {"status": "Good", "color": "#65a30d", "class": "health-good"}
    if score >= 50: return {"status": "Warning", "color": "#ca8a04", "class": "health-warning"}
    return {"status": "Critical", "color": "#dc2626", "class": "health-critical"}

def create_health_gauge(score, title="Health Score"):
    """Creates a gauge chart for health score."""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title},
        delta = {'reference': 80},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 50], 'color': "lightgray"},
                {'range': [50, 80], 'color': "gray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    fig.update_layout(height=300)
    return fig

# NUOVO: Funzione per generare un report in formato Markdown
def generate_markdown_report(dag_id, dag_content):
    """Generates a comprehensive report in Markdown format for a specific DAG."""
    ai = dag_content.get('ai_analysis', {})
    raw = dag_content.get('raw_data', {})
    stats = raw.get('stats', {})
    audit = raw.get('code_audit', {})
    errors = raw.get('log_errors', [])
    
    report_lines = []
    
    # Header
    report_lines.append(f"# 🔬 Intelligence Report for DAG: {dag_id}")
    report_lines.append(f"**Report Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("\n---\n")
    
    # Overall Status
    report_lines.append("## 📊 Overall Status")
    report_lines.append(f"- **Priority:** {ai.get('priority', 'N/A')}")
    report_lines.append(f"- **Health Score:** {ai.get('health_score', 'N/A')}%")
    report_lines.append("\n---\n")
    
    # AI Analysis
    report_lines.append("## 🤖 AI Analysis & Insights")
    report_lines.append("### Executive Summary")
    report_lines.append(f"> {ai.get('executive_summary', 'No summary available.')}")
    report_lines.append("\n### Key Recommendations")
    recommendations = ai.get('key_recommendations', [])
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            report_lines.append(f"{i}. {rec}")
    else:
        report_lines.append("No specific recommendations provided.")
    report_lines.append("\n---\n")

    # Performance Metrics
    report_lines.append("## 📈 Performance Metrics")
    if stats:
        report_lines.append("| Metric | Value |")
        report_lines.append("|---|---|")
        for key, value in stats.items():
            report_lines.append(f"| {key.replace('_', ' ')} | {value} |")
    else:
        report_lines.append("No performance statistics available.")
    report_lines.append("\n---\n")

    # Code Audit
    report_lines.append("## 🔍 Code Audit")
    if audit:
        report_lines.append(f"**Risk Level:** {audit.get('risk_level', 'N/A')}")
        report_lines.append(f"**Summary:** {audit.get('summary', 'N/A')}")
        report_lines.append("\n**Identified Issues:**")
        problems = audit.get('problems', [])
        if problems:
            for prob in problems:
                report_lines.append(f"- `{prob}`")
        else:
            report_lines.append("No issues identified.")
        
        report_lines.append("\n**Suggested Fix:**")
        code_fix = audit.get('code_fix')
        if code_fix:
            report_lines.append(f"```python\n{code_fix}\n```")
        else:
            report_lines.append("No code fix suggested.")
    else:
        report_lines.append("No code audit data available.")
    report_lines.append("\n---\n")

    # Error Logs
    report_lines.append("## 📜 Error Log Analysis")
    if errors:
        for i, log in enumerate(errors, 1):
            report_lines.append(f"### Error #{i}")
            report_lines.append(f"- **Severity:** {log.get('severity', 'UNKNOWN')}")
            report_lines.append(f"- **Error Line:**")
            report_lines.append(f"  ```\n{log.get('error', {}).get('error_line', 'N/A')}\n  ```")
            report_lines.append(f"- **AI Suggested Solution:** {log.get('suggestion', 'No suggestion available.')}")
            report_lines.append("")
    else:
        report_lines.append("No recent errors found.")
        
    return "\n".join(report_lines)

# NUOVO: Funzione per generare una stringa JSON dai dati del DAG
def generate_json_report(dag_content):
    """Generates a JSON string from the DAG content."""
    return json.dumps(dag_content, indent=2)

def display_overview_metrics(all_dags_data):
    """Display high-level dashboard metrics."""
    st.markdown('<div class="main-header"><h1>🔬 DAG Intelligence Dashboard</h1><p>Comprehensive monitoring and analysis of your data pipelines</p></div>', unsafe_allow_html=True)
    
    total_dags = len(all_dags_data)
    priority_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    health_scores = []
    
    for dag_data in all_dags_data.values():
        ai_analysis = dag_data.get('ai_analysis', {})
        priority = ai_analysis.get('priority', 'UNKNOWN')
        if priority in priority_counts:
            priority_counts[priority] += 1
        
        health_score = ai_analysis.get('health_score', 0)
        health_scores.append(health_score)
    
    avg_health = sum(health_scores) / len(health_scores) if health_scores else 0
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(label="Total DAGs", value=total_dags)
    with col2:
        st.metric(label="Critical Issues", value=priority_counts["CRITICAL"], delta_color="inverse")
    with col3:
        st.metric(label="High Priority", value=priority_counts["HIGH"], delta_color="inverse")
    with col4:
        st.metric(label="Average Health", value=f"{avg_health:.1f}%", delta=f"{avg_health - 80:.1f}%" if avg_health > 0 else None)
    with col5:
        healthy_dags = sum(1 for score in health_scores if score >= 80)
        st.metric(label="Healthy DAGs", value=f"{healthy_dags}/{total_dags}", delta=f"{(healthy_dags/total_dags)*100:.1f}%" if total_dags > 0 else None)

def display_dag_grid(filtered_dags):
    """Display DAGs in an improved grid layout."""
    st.subheader("📊 DAG Health Overview")
    
    if not filtered_dags:
        st.info("No DAGs match your current filters. Try adjusting the search or priority filters.")
        return
    
    cols_per_row = 2
    for i in range(0, len(filtered_dags), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(filtered_dags):
                dag_id, dag_content = filtered_dags[i + j]
                with col:
                    with st.container():
                        ai = dag_content.get('ai_analysis', {})
                        priority = ai.get('priority', 'UNKNOWN')
                        health_score = ai.get('health_score', 0)
                        priority_config = get_priority_config(priority)
                        health_config = get_health_status(health_score)
                        
                        st.markdown(f"""
                        <div class="dag-card {priority_config['class']}">
                            <h3>{priority_config['emoji']} {dag_id}</h3>
                        """, unsafe_allow_html=True)
                        
                        metric_col1, metric_col2 = st.columns(2)
                        with metric_col1:
                            st.metric("Health Score", f"{health_score}%")
                        with metric_col2:
                            st.metric("Priority", priority)
                        
                        st.progress(health_score / 100, text=f"Health: {health_config['status']}")
                        summary = ai.get('executive_summary', 'No summary available.')
                        st.caption(f"{summary[:150]}..." if len(summary) > 150 else summary)
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("🔍 Details", key=f"btn_details_{dag_id}", use_container_width=True):
                                st.session_state.selected_dag = dag_id
                                st.rerun()
                        with col_btn2:
                            if st.button("📈 Analytics", key=f"btn_analytics_{dag_id}", use_container_width=True):
                                st.session_state.selected_dag = dag_id
                                st.session_state.view_mode = "analytics"
                                st.rerun()
                        
                        st.markdown("</div>", unsafe_allow_html=True)

def display_dag_details(dag_id, dag_content):
    """Enhanced DAG details view with better organization."""
    ai = dag_content.get('ai_analysis', {})
    raw = dag_content.get('raw_data', {})
    priority = ai.get('priority', 'UNKNOWN')
    health_score = ai.get('health_score', 0)
    priority_config = get_priority_config(priority)
    health_config = get_health_status(health_score)
    
    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown(f"# {priority_config['emoji']} {dag_id}")
        st.markdown(f"<span class='{health_config['class']}'>Health Status: {health_config['status']}</span>", unsafe_allow_html=True)
    with col2:
        if st.button("⬅️ Back to Overview", use_container_width=True):
            st.session_state.selected_dag = None
            if 'view_mode' in st.session_state:
                del st.session_state.view_mode
            st.rerun()
    
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        fig = create_health_gauge(health_score)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.metric("Priority Level", priority)
        st.metric("Current Status", health_config['status'])
    with col3:
        stats = raw.get('stats', {})
        success_rate = stats.get('Success_Rate', 0.0)
        st.metric("Success Rate", f"{success_rate}%")
        if success_rate >= 95: st.success("Excellent performance")
        elif success_rate >= 85: st.warning("Good performance")
        else: st.error("Needs attention")
    with col4:
        stats = raw.get('stats', {})
        last_run = stats.get('Last_Run', 'N/A')
        st.metric("Last Run", last_run)
        total_runs = stats.get('Total_Runs', 0)
        st.metric("Total Runs", total_runs)
    
    st.subheader("🤖 AI Analysis & Insights")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        with st.expander("Executive Summary", expanded=True):
            st.markdown(ai.get('executive_summary', "No summary available."))
        with st.expander("Key Recommendations", expanded=True):
            recommendations = ai.get('key_recommendations', [])
            if recommendations:
                for i, rec in enumerate(recommendations, 1):
                    st.markdown(f"**{i}.** {rec}")
            else:
                st.info("No recommendations available.")
    with col2:
        st.subheader("Quick Actions")
        # Il pulsante "Refresh Analysis" ora dovrebbe ricaricare solo la dashboard, non rieseguire l'analisi AI
        # per coerenza con il nuovo flusso. L'analisi AI si fa tramite report_merger_agent.py
        if st.button("🔄 Ricarica Dashboard", use_container_width=True):
            st.cache_data.clear() # Cancella la cache per forzare il ricaricamento del JSON
            st.rerun()
        if st.button("📊 View Analytics", use_container_width=True):
            st.session_state.view_mode = "analytics"
            st.rerun()
        
        # MODIFICATO: Sostituito il vecchio pulsante con un popover per l'esportazione
        with st.popover("📥 Export Report", use_container_width=True):
            st.markdown("##### Select Export Format")
            
            # Genera i report in memoria
            markdown_report = generate_markdown_report(dag_id, dag_content)
            json_report = generate_json_report(dag_content)
            
            # Pulsante per scaricare come Markdown
            st.download_button(
                label="📄 Download as Markdown (.md)",
                data=markdown_report,
                file_name=f"{dag_id}_report_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                use_container_width=True
            )
            
            # Pulsante per scaricare come JSON
            st.download_button(
                label="💾 Download as JSON",
                data=json_report,
                file_name=f"{dag_id}_data_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    st.subheader("📋 Detailed Analysis")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Performance", "🔍 Code Audit", "📜 Error Logs", "📈 Trends"])
    
    with tab1:
        display_performance_stats(raw.get('stats', {}))
    with tab2:
        display_code_audit(raw.get('code_audit', {}))
    with tab3:
        display_error_logs(raw.get('log_errors', []))
    with tab4:
        display_trends_analysis(dag_id, raw.get('stats', {}))

def display_performance_stats(stats):
    if not stats:
        st.info("No performance statistics available.")
        return
    
    # Crea il DataFrame come prima
    df = pd.DataFrame.from_dict(stats, orient='index', columns=['Value'])
    df.index.name = "Metric"
    
    # --- LA CORREZIONE È QUI ---
    # Converte l'intera colonna 'Value' in stringhe per evitare errori di tipo con PyArrow.
    # Questo è il modo più robusto per gestire colonne con tipi di dati misti.
    df['Value'] = df['Value'].astype(str)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Performance Metrics")
        # Ora st.dataframe non avrà problemi a visualizzare il DataFrame
        st.dataframe(df, use_container_width=True)
    with col2:
        st.subheader("Key Performance Indicators")
        numeric_stats = {}
        for key, value in stats.items():
            try:
                # Tenta di convertire i valori in float per il grafico, ignorando quelli non numerici
                numeric_stats[key] = float(value)
            except (ValueError, TypeError):
                continue
        
        if numeric_stats:
            # Crea un DataFrame separato per il grafico, basato solo sui dati numerici
            numeric_df = pd.DataFrame(list(numeric_stats.items()), columns=['Metric', 'Value'])
            fig = px.bar(
                numeric_df,
                x='Metric',
                y='Value',
                title="Performance Metrics Overview"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No numeric metrics available for charting.")

def display_code_audit(audit):
    if not audit:
        st.info("No code audit data available.")
        return
    
    risk_level = audit.get('risk_level', 'UNKNOWN')
    if risk_level == 'HIGH': st.error(f"🚨 Risk Level: {risk_level}")
    elif risk_level == 'MEDIUM': st.warning(f"⚠️ Risk Level: {risk_level}")
    else: st.success(f"✅ Risk Level: {risk_level}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Audit Summary")
        st.info(audit.get('summary', 'No summary available.'))
        st.subheader("Recommendations")
        st.warning(audit.get('suggestion', 'No suggestions available.'))
    with col2:
        st.subheader("Identified Issues")
        problems = audit.get('problems', [])
        if problems:
            for i, problem in enumerate(problems, 1):
                st.markdown(f"**{i}.** `{problem}`")
        else:
            st.success("No issues identified!")
    
    code_fix = audit.get('code_fix')
    if code_fix:
        st.subheader("Suggested Code Improvements")
        st.code(code_fix, language='python')

def display_error_logs(logs):
    if not logs:
        st.success("No recent errors found! 🎉")
        return
    st.warning(f"Found {len(logs)} error(s) that need attention")

    for i, log in enumerate(logs, 1):
        with st.expander(f"Error #{i} - {log.get('severity', 'UNKNOWN').title()} Severity", expanded=(i == 1)):

            st.markdown("**Error Details:**")
            st.code(log.get('error', {}).get('error_line', 'N/A'), language='log')
            st.divider()
            st.markdown("**AI Analysis & Solution:**")
            st.markdown(log.get('suggestion', 'No suggestion available.'))

def display_trends_analysis(dag_id, stats):
    st.info("Trends analysis would show historical performance data here.")
    import numpy as np
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    success_rates = np.clip(np.random.normal(85, 10, len(dates)), 0, 100)
    fig = px.line(x=dates, y=success_rates, title=f"Success Rate Trend for {dag_id}", labels={'x': 'Date', 'y': 'Success Rate (%)'})
    st.plotly_chart(fig, use_container_width=True)

def create_sidebar():
    with st.sidebar:
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.header("🎛️ Dashboard Controls")
        if st.session_state.get('selected_dag'):
            if st.button("⬅️ Back to Overview", use_container_width=True):
                st.session_state.selected_dag = None
                if 'view_mode' in st.session_state: del st.session_state.view_mode
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.subheader("🔍 Filters")
        search_query = st.text_input("Search DAGs", placeholder="Enter DAG name...", key="search")
        priority_options = ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
        selected_priority = st.selectbox("Priority Level", priority_options, key="priority_filter")
        health_threshold = st.slider("Minimum Health Score", 0, 100, 0, key="health_filter")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.subheader("📈 Quick Stats")
        st.info("Real-time dashboard statistics would appear here")
        st.markdown('</div>', unsafe_allow_html=True)
        
        return search_query, selected_priority, health_threshold

def main():
    if 'selected_dag' not in st.session_state:
        st.session_state.selected_dag = None
    if 'view_mode' not in st.session_state:
        st.session_state.view_mode = 'details'
    
    all_dags_data = load_data()
    
    # La gestione dell'errore per il mancato caricamento dei dati è ora gestita in load_data() con st.stop()
    # Quindi questa condizione non dovrebbe più essere necessaria qui direttamente dopo la chiamata a load_data().
    # Tuttavia, se load_data() restituisce un dizionario vuoto a causa di un problema non fatale,
    # è comunque utile gestire il caso qui.
    if not all_dags_data:
        # Se load_data() ha chiamato st.stop(), il codice non arriverà qui.
        # Se invece è stato un errore meno grave e ha ritornato {}, avvisa comunque.
        st.error("I dati dei DAG non sono disponibili. Per favore, assicurati che il file `final_dashboard_data.json` sia stato generato correttamente.")
        st.stop() # Aggiunto st.stop() anche qui per sicurezza, se il primo stop non ha funzionato.

    search_query, selected_priority, health_threshold = create_sidebar()
    
    priority_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
    
    filtered_dags = []
    for dag_id, data in all_dags_data.items():
        ai_analysis = data.get('ai_analysis', {})
        priority = ai_analysis.get('priority', 'UNKNOWN')
        health_score = ai_analysis.get('health_score', 0)
        
        if search_query and search_query.lower() not in dag_id.lower(): continue
        if selected_priority != "All" and priority != selected_priority: continue
        if health_score < health_threshold: continue
        
        filtered_dags.append((dag_id, data))
    
    filtered_dags.sort(
        key=lambda x: priority_map.get(x[1].get('ai_analysis', {}).get('priority', 'UNKNOWN'), 0),
        reverse=True
    )
    
    if st.session_state.selected_dag:
        display_dag_details(st.session_state.selected_dag, all_dags_data[st.session_state.selected_dag])
    else:
        display_overview_metrics(all_dags_data)
        display_dag_grid(filtered_dags)

if __name__ == "__main__":
    main()