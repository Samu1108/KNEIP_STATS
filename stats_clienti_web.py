import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import pandas as pd
from firebase_admin import credentials, firestore, initialize_app

# === CONFIGURAZIONE FIREBASE ===
cred = credentials.Certificate("/home/sarto/Desktop/STATS_KNEIP/serviceAccountKey.json")
initialize_app(cred)
db = firestore.client()

# === LETTURA DATI ===
docs = db.collection("clienti").stream()
clienti = [doc.to_dict() for doc in docs]
df = pd.DataFrame(clienti)

# === APP DASH ===
app = dash.Dash(__name__)
app.title = "Stats Clienti Web"

# === LAYOUT ===
app.layout = html.Div(style={'fontFamily':'Arial','margin':'20px','backgroundColor':'#f5f7fa'}, children=[
    html.H1("Stats Clienti", style={'textAlign':'center', 'marginBottom':'30px', 'color':'#1f77b4'}),
    
    html.Div([
        html.Label("Seleziona la data:", style={'fontWeight':'bold'}),
        dcc.Dropdown(
            id='dropdown-data',
            options=[{'label': d, 'value': d} for d in sorted(df['data'].dropna().unique())] + [{'label':'Tutti i dati','value':'all'}],
            value='all',
            style={'width':'300px', 'marginRight':'20px'}
        ),
        html.Button("Analizza", id='btn-analizza', n_clicks=0, 
                    style={'backgroundColor':'#1f77b4','color':'white','border':'none',
                           'padding':'5px 15px','cursor':'pointer','fontWeight':'bold'})
    ], style={'display':'flex','alignItems':'center','marginBottom':'20px'}),
    
    dcc.Graph(id='grafico-clienti', style={'height':'400px', 'marginBottom':'30px'}),
    
    html.Div(id='analisi-breve', style={'marginBottom':'20px', 'fontWeight':'bold', 'fontSize':'18px'}),
    
    dash_table.DataTable(
        id='tabella-clienti',
        columns=[{"name": i, "id": i} for i in ["Fascia Oraria","Adulti","Bambini","Totale","Incasso Adulti","Incasso Bambini","Incasso Totale"]],
        data=[],  # inizialmente vuota
        style_cell={'textAlign':'center', 'padding':'10px', 'fontSize':'14px'},
        style_header={'backgroundColor':'#1f77b4','color':'white','fontWeight':'bold','fontSize':'15px'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'},
            {'if': {'row_index': 'even'}, 'backgroundColor': '#e0f0ff'},
            {'if': {'filter_query': '{Fascia Oraria} = "TOTALE"'},
             'backgroundColor': '#ffd700', 'fontWeight': 'bold', 'fontSize':'16px', 'color':'black'}
        ],
        style_table={
            'overflowX':'auto',
            'border':'1px solid #ccc',
            'borderRadius':'5px',
            'marginBottom':'50px',
            'minWidth':'900px'
        },
        fixed_columns={'headers': True, 'data': 1},  
        style_cell_conditional=[
            {'if': {'column_id': 'Fascia Oraria'}, 'textAlign':'left', 'width':'150px', 'minWidth':'150px', 'maxWidth':'150px'}
        ],
        page_action='none',
        style_as_list_view=True
    )
])

# === CALLBACK PER ANALISI ===
@app.callback(
    [Output('grafico-clienti', 'figure'),
     Output('tabella-clienti', 'data'),
     Output('analisi-breve', 'children')],
    [Input('btn-analizza', 'n_clicks')],
    [State('dropdown-data', 'value')]
)
def aggiorna_analisi(n_clicks, selected_date):
    if n_clicks == 0:
        return {}, [], ""
    
    dati = df.copy()
    if selected_date != 'all':
        dati = dati[dati['data'] == selected_date]
    
    if dati.empty:
        return {}, [], "Nessun dato disponibile per la selezione."
    
    # Creazione fascia oraria (30 min)
    dati['orario'] = dati['orario'].fillna("00:00")
    def fascia_30min(o):
        try:
            h, m = map(int, o.split(":"))
            m = 0 if m < 30 else 30
            return f"{h:02d}:{m:02d}"
        except:
            return "00:00"
    dati['fascia'] = dati['orario'].apply(fascia_30min)
    
    # Aggregazione per fascia
    fasce = dati.groupby('fascia').agg(
        Adulti = ('descrizione', lambda x: sum('bamb' not in i.lower() for i in x)),
        Bambini = ('descrizione', lambda x: sum('bamb' in i.lower() for i in x))
    ).reset_index()
    
    # Rinomina colonna per la DataTable
    fasce.rename(columns={'fascia': 'Fascia Oraria'}, inplace=True)
    
    fasce['Totale'] = fasce['Adulti'] + fasce['Bambini']
    fasce['Incasso Adulti'] = fasce['Adulti']*3
    fasce['Incasso Bambini'] = fasce['Bambini']*2
    fasce['Incasso Totale'] = fasce['Incasso Adulti'] + fasce['Incasso Bambini']
    
    # Totali assoluti
    tot_row = {
        "Fascia Oraria": "TOTALE",
        "Adulti": fasce['Adulti'].sum(),
        "Bambini": fasce['Bambini'].sum(),
        "Totale": fasce['Totale'].sum(),
        "Incasso Adulti": fasce['Incasso Adulti'].sum(),
        "Incasso Bambini": fasce['Incasso Bambini'].sum(),
        "Incasso Totale": fasce['Incasso Totale'].sum()
    }
    fasce = pd.concat([fasce, pd.DataFrame([tot_row])], ignore_index=True)
    
    # Aggiunta simbolo euro agli incassi
    for col in ['Incasso Adulti', 'Incasso Bambini', 'Incasso Totale']:
        fasce[col] = fasce[col].apply(lambda x: f"{x} €")
    
    # Analisi breve
    analisi_text = f"Totali: Adulti={tot_row['Adulti']}, Bambini={tot_row['Bambini']}, Clienti={tot_row['Totale']}, Incasso={tot_row['Incasso Totale']} €"
    
    # Grafico con Adulti e Bambini
    fig = {
        'data': [
            {'x': fasce['Fascia Oraria'][:-1], 'y': fasce['Adulti'][:-1], 'type':'bar', 'name':'Adulti','marker':{'color':'#1f77b4'}},
            {'x': fasce['Fascia Oraria'][:-1], 'y': fasce['Bambini'][:-1], 'type':'bar', 'name':'Bambini','marker':{'color':'#ff7f0e'}}
        ],
        'layout':{'title':f'Clienti per Fascia Oraria ({selected_date})', 
                  'xaxis_title':'Fascia Oraria', 'yaxis_title':'Numero Clienti', 'barmode':'stack'}
    }
    
    return fig, fasce.to_dict('records'), analisi_text

# === AVVIO SERVER ===
if __name__ == '__main__':
    app.run(debug=True)

