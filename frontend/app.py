"""
Dash frontend for Cancer Biomarker Identifier.
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import requests
import json
import base64
import io
from datetime import datetime
import time

# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True
)

app.title = "Cancer Biomarker Identifier"

# API base URL
API_BASE_URL = "http://localhost:8000/api"

# App layout
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.H1("Cancer Biomarker Identifier", className="text-center mb-3"),
            html.P("A comprehensive tool for identifying, validating, and visualizing cancer biomarkers", 
                   className="text-center text-muted mb-4")
        ])
    ]),
    
    # Navigation tabs
    dbc.Tabs([
        # Data Upload Tab
        dbc.Tab([
            dbc.Card([
                dbc.CardBody([
                    html.H4("Data Upload", className="card-title"),
                    html.P("Upload your expression data and sample labels to start biomarker identification."),
                    
                    # File upload section
                    dbc.Row([
                        dbc.Col([
                            html.Label("Expression Data File (TSV/CSV)"),
                            dcc.Upload(
                                id='upload-expression',
                                children=html.Div([
                                    'Drag and Drop or ',
                                    html.A('Select Files')
                                ]),
                                style={
                                    'width': '100%',
                                    'height': '60px',
                                    'lineHeight': '60px',
                                    'borderWidth': '1px',
                                    'borderStyle': 'dashed',
                                    'borderRadius': '5px',
                                    'textAlign': 'center',
                                    'margin': '10px'
                                },
                                multiple=False
                            ),
                            html.Div(id='expression-upload-status')
                        ], width=6),
                        
                        dbc.Col([
                            html.Label("Sample Labels File (TSV/CSV)"),
                            dcc.Upload(
                                id='upload-labels',
                                children=html.Div([
                                    'Drag and Drop or ',
                                    html.A('Select Files')
                                ]),
                                style={
                                    'width': '100%',
                                    'height': '60px',
                                    'lineHeight': '60px',
                                    'borderWidth': '1px',
                                    'borderStyle': 'dashed',
                                    'borderRadius': '5px',
                                    'textAlign': 'center',
                                    'margin': '10px'
                                },
                                multiple=False
                            ),
                            html.Div(id='labels-upload-status')
                        ], width=6)
                    ]),
                    
                    # Configuration section
                    dbc.Row([
                        dbc.Col([
                            html.H5("Pipeline Configuration", className="mt-4"),
                            
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Run Name"),
                                    dbc.Input(id="run-name", placeholder="Enter run name", type="text")
                                ], width=6),
                                dbc.Col([
                                    html.Label("Normalization Method"),
                                    dcc.Dropdown(
                                        id="normalization-method",
                                        options=[
                                            {"label": "Log2", "value": "log2"},
                                            {"label": "Z-score", "value": "z_score"},
                                            {"label": "Quantile", "value": "quantile"},
                                            {"label": "TMM", "value": "tmm"}
                                        ],
                                        value="log2"
                                    )
                                ], width=6)
                            ]),
                            
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Statistical Test"),
                                    dcc.Dropdown(
                                        id="statistical-test",
                                        options=[
                                            {"label": "Welch t-test", "value": "welch_t"},
                                            {"label": "Wilcoxon", "value": "wilcoxon"},
                                            {"label": "ANOVA", "value": "anova"}
                                        ],
                                        value="welch_t"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Significance Level"),
                                    dbc.Input(id="alpha", value=0.05, type="number", step=0.01, min=0, max=1)
                                ], width=6)
                            ]),
                            
                            dbc.Row([
                                dbc.Col([
                                    html.Label("ML Models"),
                                    dcc.Checklist(
                                        id="ml-models",
                                        options=[
                                            {"label": "Logistic Regression", "value": "logistic_regression"},
                                            {"label": "Random Forest", "value": "random_forest"},
                                            {"label": "SVM", "value": "svm"},
                                            {"label": "XGBoost", "value": "xgboost"}
                                        ],
                                        value=["logistic_regression", "random_forest"]
                                    )
                                ], width=12)
                            ])
                        ])
                    ]),
                    
                    # Start pipeline button
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(
                                "Start Biomarker Pipeline",
                                id="start-pipeline",
                                color="primary",
                                size="lg",
                                className="mt-3 w-100"
                            )
                        ])
                    ]),
                    
                    # Pipeline status
                    html.Div(id="pipeline-status")
                ])
            ])
        ], label="Data Upload", tab_id="upload"),
        
        # Pipeline Monitoring Tab
        dbc.Tab([
            dbc.Card([
                dbc.CardBody([
                    html.H4("Pipeline Monitoring", className="card-title"),
                    
                    # Run selection
                    dbc.Row([
                        dbc.Col([
                            html.Label("Select Run"),
                            dcc.Dropdown(id="run-selector", placeholder="Select a pipeline run")
                        ], width=6),
                        dbc.Col([
                            dbc.Button("Refresh Runs", id="refresh-runs", color="secondary", className="mt-4")
                        ], width=6)
                    ]),
                    
                    # Run status
                    html.Div(id="run-status-display"),
                    
                    # Progress indicators
                    html.Div(id="pipeline-progress")
                ])
            ])
        ], label="Pipeline Monitoring", tab_id="monitoring"),
        
        # Results Tab
        dbc.Tab([
            dbc.Card([
                dbc.CardBody([
                    html.H4("Analysis Results", className="card-title"),
                    
                    # Results navigation
                    dbc.Tabs([
                        dbc.Tab([
                            html.Div(id="biomarker-results")
                        ], label="Biomarkers"),
                        
                        dbc.Tab([
                            html.Div(id="statistical-results")
                        ], label="Statistical Analysis"),
                        
                        dbc.Tab([
                            html.Div(id="ml-results")
                        ], label="Machine Learning"),
                        
                        dbc.Tab([
                            html.Div(id="pathway-results")
                        ], label="Pathway Analysis"),
                        
                        dbc.Tab([
                            html.Div(id="annotation-results")
                        ], label="Annotation")
                    ])
                ])
            ])
        ], label="Results", tab_id="results"),
        
        # Reports Tab
        dbc.Tab([
            dbc.Card([
                dbc.CardBody([
                    html.H4("Reports", className="card-title"),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Label("Report Format"),
                            dcc.Dropdown(
                                id="report-format",
                                options=[
                                    {"label": "HTML", "value": "html"},
                                    {"label": "PDF", "value": "pdf"}
                                ],
                                value="html"
                            )
                        ], width=4),
                        dbc.Col([
                            html.Label("Report Title"),
                            dbc.Input(id="report-title", placeholder="Enter report title")
                        ], width=4),
                        dbc.Col([
                            dbc.Button("Generate Report", id="generate-report", color="success", className="mt-4")
                        ], width=4)
                    ]),
                    
                    html.Div(id="report-status")
                ])
            ])
        ], label="Reports", tab_id="reports")
    ], id="main-tabs"),
    
    # Store components
    dcc.Store(id="uploaded-data"),
    dcc.Store(id="current-run-id"),
    dcc.Store(id="pipeline-results"),
    
    # Interval for polling
    dcc.Interval(
        id='interval-component',
        interval=5*1000,  # 5 seconds
        n_intervals=0,
        disabled=True
    )
], fluid=True)

# Callbacks

@app.callback(
    [Output("expression-upload-status", "children"),
     Output("labels-upload-status", "children")],
    [Input("upload-expression", "contents"),
     Input("upload-labels", "contents")],
    [State("upload-expression", "filename"),
     State("upload-labels", "filename")]
)
def handle_file_upload(expression_contents, labels_contents, expression_filename, labels_filename):
    """Handle file uploads and display status."""
    ctx = callback_context
    
    if not ctx.triggered:
        return "", ""
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == "upload-expression" and expression_contents:
        return dbc.Alert(f"✓ {expression_filename} uploaded successfully", color="success"), ""
    elif trigger_id == "upload-labels" and labels_contents:
        return "", dbc.Alert(f"✓ {labels_filename} uploaded successfully", color="success")
    
    return "", ""

@app.callback(
    [Output("pipeline-status", "children"),
     Output("current-run-id", "data"),
     Output("interval-component", "disabled")],
    [Input("start-pipeline", "n_clicks")],
    [State("upload-expression", "contents"),
     State("upload-labels", "contents"),
     State("run-name", "value"),
     State("normalization-method", "value"),
     State("statistical-test", "value"),
     State("alpha", "value"),
     State("ml-models", "value")]
)
def start_pipeline(n_clicks, expression_contents, labels_contents, run_name, 
                  norm_method, stat_test, alpha, ml_models):
    """Start the biomarker identification pipeline."""
    if not n_clicks or not expression_contents or not labels_contents:
        return "", None, True
    
    try:
        # Prepare configuration
        config = {
            "normalization_method": norm_method,
            "stats_methods": [stat_test],
            "alpha": alpha,
            "selection_methods": ml_models
        }
        
        # Prepare files for upload
        files = {
            'expression_file': ('expression.tsv', expression_contents.split(',')[1]),
            'labels_file': ('labels.tsv', labels_contents.split(',')[1])
        }
        
        data = {
            'run_name': run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'config': json.dumps(config)
        }
        
        # Start pipeline
        response = requests.post(f"{API_BASE_URL}/biomarkers/run", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            run_id = result["run_id"]
            
            status_card = dbc.Card([
                dbc.CardBody([
                    html.H5("Pipeline Started", className="card-title text-success"),
                    html.P(f"Run ID: {run_id}"),
                    html.P("Pipeline is now running in the background. Monitor progress in the Pipeline Monitoring tab.")
                ])
            ])
            
            return status_card, run_id, False
        else:
            error_msg = response.json().get("detail", "Unknown error")
            return dbc.Alert(f"Error starting pipeline: {error_msg}", color="danger"), None, True
            
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger"), None, True

@app.callback(
    [Output("run-selector", "options"),
     Output("run-selector", "value")],
    [Input("refresh-runs", "n_clicks"),
     Input("interval-component", "n_intervals")]
)
def update_run_list(n_clicks, n_intervals):
    """Update the list of available runs."""
    try:
        response = requests.get(f"{API_BASE_URL}/biomarkers/runs")
        if response.status_code == 200:
            runs = response.json()["runs"]
            options = [{"label": f"{run['run_id']} ({run['status']})", "value": run['run_id']} 
                      for run in runs]
            return options, None
        else:
            return [], None
    except:
        return [], None

@app.callback(
    [Output("run-status-display", "children"),
     Output("pipeline-progress", "children")],
    [Input("run-selector", "value"),
     Input("interval-component", "n_intervals")]
)
def update_run_status(run_id, n_intervals):
    """Update the status display for the selected run."""
    if not run_id:
        return "", ""
    
    try:
        response = requests.get(f"{API_BASE_URL}/biomarkers/runs/{run_id}/status")
        if response.status_code == 200:
            status_data = response.json()
            
            # Status card
            status_color = "success" if status_data["status"] == "completed" else \
                          "danger" if status_data["status"] == "failed" else "warning"
            
            status_card = dbc.Card([
                dbc.CardBody([
                    html.H5(f"Status: {status_data['status'].title()}", 
                           className=f"card-title text-{status_color}"),
                    html.P(f"Run ID: {run_id}"),
                    html.P(f"Last Updated: {status_data['timestamp']}")
                ])
            ])
            
            # Progress indicators
            if status_data["status"] == "running":
                progress = dbc.Card([
                    dbc.CardBody([
                        html.H6("Pipeline Progress"),
                        dbc.Progress(value=50, label="Processing...", className="mb-3"),
                        html.P("Pipeline is currently running. This may take several minutes.")
                    ])
                ])
            elif status_data["status"] == "completed":
                progress = dbc.Card([
                    dbc.CardBody([
                        html.H6("Pipeline Complete"),
                        dbc.Progress(value=100, label="Complete", color="success", className="mb-3"),
                        html.P("Pipeline has completed successfully. View results in the Results tab.")
                    ])
                ])
            else:
                progress = ""
            
            return status_card, progress
        else:
            return dbc.Alert("Error fetching run status", color="danger"), ""
    except:
        return dbc.Alert("Error fetching run status", color="danger"), ""

@app.callback(
    Output("biomarker-results", "children"),
    [Input("run-selector", "value")]
)
def display_biomarker_results(run_id):
    """Display biomarker results."""
    if not run_id:
        return html.P("Select a run to view biomarker results.")
    
    try:
        response = requests.get(f"{API_BASE_URL}/biomarkers/runs/{run_id}/biomarkers")
        if response.status_code == 200:
            data = response.json()
            biomarkers = data["biomarkers"]
            
            if not biomarkers:
                return html.P("No biomarkers found.")
            
            # Create DataFrame for display
            df = pd.DataFrame(biomarkers)
            
            # Create table
            table = dbc.Table.from_dataframe(
                df.head(20), 
                striped=True, 
                bordered=True, 
                hover=True,
                className="mt-3"
            )
            
            # Create summary cards
            summary_cards = dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(str(data["total_count"]), className="card-title"),
                            html.P("Total Biomarkers", className="card-text")
                        ])
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(str(len([b for b in biomarkers if b.get("final_score", 0) > 0.7])), 
                                   className="card-title"),
                            html.P("High Confidence", className="card-text")
                        ])
                    ])
                ], width=3)
            ])
            
            return html.Div([
                summary_cards,
                html.H5("Top Biomarkers", className="mt-4"),
                table
            ])
        else:
            return dbc.Alert("Error fetching biomarker results", color="danger")
    except:
        return dbc.Alert("Error fetching biomarker results", color="danger")

@app.callback(
    Output("report-status", "children"),
    [Input("generate-report", "n_clicks")],
    [State("run-selector", "value"),
     State("report-format", "value"),
     State("report-title", "value")]
)
def generate_report(n_clicks, run_id, report_format, report_title):
    """Generate a report for the selected run."""
    if not n_clicks or not run_id:
        return ""
    
    try:
        data = {
            "report_format": report_format,
            "report_title": report_title or f"Biomarker Report - {run_id}"
        }
        
        response = requests.post(f"{API_BASE_URL}/biomarkers/runs/{run_id}/report", json=data)
        
        if response.status_code == 200:
            result = response.json()
            return dbc.Alert([
                html.H6("Report Generated Successfully"),
                html.P(f"Report saved to: {result['report_path']}"),
                dbc.Button("Download Report", 
                          href=f"{API_BASE_URL}/biomarkers/runs/{run_id}/download-report?format={report_format}",
                          color="primary",
                          className="mt-2")
            ], color="success")
        else:
            error_msg = response.json().get("detail", "Unknown error")
            return dbc.Alert(f"Error generating report: {error_msg}", color="danger")
    except Exception as e:
        return dbc.Alert(f"Error: {str(e)}", color="danger")

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)
