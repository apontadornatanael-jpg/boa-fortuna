# Certifique-se de incluir estas importações no topo do seu app.py:
# from openpyxl.chart import BarChart, LineChart, Reference

def gerar_excel_formatado(df_manobras, df_paradas, id_furo):
    wb = Workbook()
    
    # ==========================================
    # ABA 1: BOLETIM DE MANOBRAS E GRÁFICO RQD
    # ==========================================
    ws = wb.active
    ws.title = f"Furo {id_furo}"
    ws.views.sheetView[0].showGridLines = True
    
    # Estilos Visuais
    cor_cabecalho = "1E293B"
    cor_linha_par = "F8FAFC"
    
    fonte_titulo = Font(name="Calibri", size=14, bold=True, color="1E293B")
    fonte_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fonte_dados = Font(name="Calibri", size=10)
    
    preenchimento_header = PatternFill(start_color=cor_cabecalho, end_color=cor_cabecalho, fill_type="solid")
    preenchimento_zebrado = PatternFill(start_color=cor_linha_par, end_color=cor_linha_par, fill_type="solid")
    
    alinhamento_centro = Alignment(horizontal="center", vertical="center")
    alinhamento_esquerda = Alignment(horizontal="left", vertical="center")
    
    borda_fina = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    # Título Principal
    ws.append([f"BOLETIM DIÁRIO DE SONDAGEM ROTATIVA - FURO: {id_furo}"])
    ws.cell(row=1, column=1).font = fonte_titulo
    ws.append([]) # Linha em branco
    
    # Cabeçalho da Tabela
    colunas = [
        "De (m)", "Até (m)", "Avanço (m)", "Recup. (m)", 
        "Recup. (%)", "RQD (m)", "RQD (%)", "Qualidade RQD", 
        "Litologia", "Caixa Nº", "Retorno Fluido"
    ]
    ws.append(colunas)
    
    linha_header = 3
    for col_idx in range(1, len(colunas) + 1):
        cell = ws.cell(row=linha_header, column=col_idx)
        cell.font = fonte_header
        cell.fill = preenchimento_header
        cell.alignment = alinhamento_centro
        cell.border = borda_fina
    
    # Dados das Manobras
    dados_cols = [
        "de_m", "ate_m", "avanco_m", "recup_m", 
        "recup_pct", "rqd_m", "rqd_pct", "qualidade_rqd", 
        "litologia", "caixa_num", "perda_agua"
    ]
    
    for r_idx, row in df_manobras[dados_cols].iterrows():
        row_num = linha_header + 1 + r_idx
        val_lista = row.tolist()
        ws.append(val_lista)
        
        is_par = (r_idx % 2 == 0)
        for c_idx in range(1, len(val_lista) + 1):
            cell = ws.cell(row=row_num, column=c_idx)
            cell.font = fonte_dados
            cell.border = borda_fina
            
            if is_par:
                cell.fill = preenchimento_zebrado
                
            # Formatação de Valores
            if c_idx in [1, 2, 3, 4, 6]:
                cell.number_format = '0.00" m"'
                cell.alignment = alinhamento_centro
            elif c_idx in [5, 7]:
                cell.number_format = '0.0"%"'
                cell.alignment = alinhamento_centro
            elif c_idx in [8, 10, 11]:
                cell.alignment = alinhamento_centro
            else:
                cell.alignment = alinhamento_esquerda

    # Ajuste de Largura das Colunas
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row >= linha_header:
                val_str = str(cell.value or '')
                if len(val_str) > max_len:
                    max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # ---------------------------------------------------------
    # 📈 INSERÇÃO DO GRÁFICO NATIVO DO EXCEL (RECUPERAÇÃO & RQD)
    # ---------------------------------------------------------
    if len(df_manobras) > 0:
        chart_rqd = LineChart()
        chart_rqd.title = "Perfil Geotécnico: Recuperação vs RQD (%)"
        chart_rqd.style = 13
        chart_rqd.y_axis.title = "Percentual (%)"
        chart_rqd.x_axis.title = "Profundidade (De)"
        chart_rqd.width = 16
        chart_rqd.height = 10
        
        # Seleção dos dados: Coluna 5 (Recup %) e Coluna 7 (RQD %)
        dados_rqd = Reference(ws, min_col=5, min_row=3, max_col=7, max_row=ws.max_row)
        categorias = Reference(ws, min_col=1, min_row=4, max_row=ws.max_row)
        
        chart_rqd.add_data(dados_rqd, titles_from_data=True)
        chart_rqd.set_categories(categorias)
        
        # Adicionar o gráfico à direita da tabela (Coluna M)
        ws.add_chart(chart_rqd, "M3")

    # ==========================================
    # ABA 2: TEMPOS IMOBILIZADOS (DOWNTIME)
    # ==========================================
    if not df_paradas.empty:
        ws_paradas = wb.create_sheet(title="Downtime & Paradas")
        ws_paradas.views.sheetView[0].showGridLines = True
        
        ws_paradas.append(["RELATÓRIO DE PARADAS E TEMPOS IMOBILIZADOS"])
        ws_paradas.cell(row=1, column=1).font = fonte_titulo
        ws_paradas.append([])
        
        col_p = ["Categoria / Motivo", "Duração (Horas)", "Observação", "Data/Hora"]
        ws_paradas.append(col_p)
        
        for col_idx in range(1, len(col_p) + 1):
            cell = ws_paradas.cell(row=3, column=col_idx)
            cell.font = fonte_header
            cell.fill = preenchimento_header
            cell.alignment = alinhamento_centro
            cell.border = borda_fina
            
        for r_idx, row in df_paradas[["categoria", "horas", "observacao", "data_hora"]].iterrows():
            row_num = 4 + r_idx
            val_lista = row.tolist()
            ws_paradas.append(val_lista)
            
            for c_idx in range(1, len(val_lista) + 1):
                cell = ws_paradas.cell(row=row_num, column=c_idx)
                cell.font = fonte_dados
                cell.border = borda_fina
                if c_idx == 2:
                    cell.number_format = '0.0" h"'
                    cell.alignment = alinhamento_centro
                else:
                    cell.alignment = alinhamento_esquerda
                    
        # 📊 GRÁFICO DE BARRAS DE DOWNTIME
        chart_bar = BarChart()
        chart_bar.type = "col"
        chart_bar.style = 10
        chart_bar.title = "Horas Paradas por Ocorrência"
        chart_bar.y_axis.title = "Horas"
        chart_bar.x_axis.title = "Motivo"
        chart_bar.width = 15
        chart_bar.height = 9
        
        dados_bar = Reference(ws_paradas, min_col=2, min_row=3, max_row=ws_paradas.max_row)
        cats_bar = Reference(ws_paradas, min_col=1, min_row=4, max_row=ws_paradas.max_row)
        
        chart_bar.add_data(dados_bar, titles_from_data=True)
        chart_bar.set_categories(cats_bar)
        
        ws_paradas.add_chart(chart_bar, "F3")

    # Retornar o ficheiro gravado em memória
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
