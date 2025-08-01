#!/usr/bin/python3
#-*-coding:UTF-8-*-
#Author: LeafLight
#Date: 2025-07-21 23:41:01
#---
import base64
import io
import numpy as np
import pandas as pd
import plotly.express as px
from PIL import Image
import dash
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable
import plotly.graph_objects as go
import logging

# 初始化Dash应用，并设置suppress_callback_exceptions=True
app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True)
server = app.server
app.title = "图像颜色分析器"

# 应用布局
app.layout = dbc.Container([
    # 标题
    dbc.Row(dbc.Col(html.H1("图像颜色分析器", className="text-center my-4"))),

    # 上传区域
    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='upload-image',
                children=html.Div([
                    "拖放图片或",
                    html.A("选择文件")
                ]),
                style={
                    'width': '100%', 'height': '200px', 'lineHeight': '200px',
                    'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '5px',
                    'textAlign': 'center', 'cursor': 'pointer', 'background': '#f8f9fa'
                },
                multiple=False
            ),
            html.Div(id='paste-area', style={
                'marginTop': '10px',
                'padding': '10px',
                'border': '1px dashed #ccc',
                'textAlign': 'center'
            }, children="或者按 Ctrl+V 粘贴图片"),
        ], width=8, className="mb-4")
    ], justify="center"),

    # 阈值控制
    dbc.Row([
        dbc.Col([
            html.Label("像素数量阈值 (只显示超过此百分比的颜色):"),
            dcc.Slider(
                id='percentage-slider',
                min=0,
                max=10,
                step=0.1,
                value=1,
                marks={i: str(i) for i in range(0, 11, 1)},
            )
        ], width=4),

        dbc.Col([
            html.Label("白色过滤阈值（RGB≥该值视为白色，不计入）:"),
            dcc.Slider(
                id='white-filter-slider', 
                min=220, 
                max=255, 
                step=1,
                value=252, 
                marks={i: str(i) for i in range(220, 256, 5)}
            )
        ], width=4),
        dbc.Col([
        html.Label("多选复制格式:"),
        dcc.Dropdown(
            id='copy-format',
            options=[
                {'label': '十六进制 (默认)', 'value': 'hex'},
                {'label': 'Python list (RGB)', 'value': 'py'},
                {'label': 'R 向量 (RGB)', 'value': 'r'}
            ],
            value='hex',  # 将默认值改为十六进制
            clearable=False
            ),
        dbc.Button("复制选中颜色", id='copy-btn', color="primary", className="mt-2"),
        html.Div(id='copy-status', className="mt-2 text-success")
        ], width=3)  # 调整宽度以适应更多选项
    ], justify="center", className="mb-4"),

    # 图像展示区域
    dbc.Row([
        dbc.Col(
            dcc.Graph(id='display-image', config={'staticPlot': False}),
            width=8, className="mb-4"
        )
    ], justify="center"),

    # 颜色表格和图表
    dbc.Row([
        dbc.Col([
            html.H4("主要颜色分析结果", className="text-center mb-3"),
            html.Div(id='color-table-container'),
            html.Div(id='color-chart-container', className="mt-4"),
            html.Div(id='dummy-output', style={'display': 'none'}),
            dcc.Store(id='pasted-image-store', data='')  # 存储粘贴的图像
        ], width=10)
    ], justify="center")
], fluid=True)

# 处理图像上传和粘贴
@app.callback(
    Output('display-image', 'figure'),
    Output('color-table-container', 'children'),
    Output('color-chart-container', 'children'),
    Output('pasted-image-store', 'data', allow_duplicate=True),  # 重置粘贴存储
    Input('upload-image', 'contents'),
    Input('pasted-image-store', 'data'),  # 添加粘贴输入
    Input('percentage-slider', 'value'),
    Input('white-filter-slider', 'value'),
    State('upload-image', 'filename'),
    prevent_initial_call=True
)
def process_image(upload_contents, pasted_content, pct_threshold, white_thresh, filename):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # 确定内容来源
    if trigger_id == 'pasted-image-store' and pasted_content:
        # 处理粘贴内容（可能是字符串或字典）
        if isinstance(pasted_content, dict) and 'content' in pasted_content:
            contents = pasted_content['content']  # 从字典中提取内容
        else:
            contents = pasted_content  # 直接使用字符串内容
        filename = "粘贴的图片"
    elif upload_contents:
        contents = upload_contents
    else:
        return no_update, no_update, no_update, no_update

    # 从base64编码中提取图像数据
    try:
        # 检查是否是完整的base64字符串（包含逗号）
        if ',' in contents:
            content_type, content_string = contents.split(',')
        else:
            content_string = contents  # 如果没有逗号，整个字符串都是内容
            
        decoded = base64.b64decode(content_string)
        image = Image.open(io.BytesIO(decoded))
    except Exception as e:
        return no_update, html.Div(f"错误: {str(e)}", className="text-danger"), no_update, no_update

    # 将图像转换为RGB数组
    img_array = np.array(image.convert('RGB'))
    h, w, _ = img_array.shape
    total_pixels = h * w

    # 重塑为像素列表
    pixels = img_array.reshape(-1, 3)

    # 获取唯一颜色及其计数
    unique_colors, counts = np.unique(pixels, axis=0, return_counts=True)

    # 创建DataFrame - 确保RGB值为整数
    df = pd.DataFrame(unique_colors.astype(int), columns=['R', 'G', 'B'])
    # 应用阈值过滤
    # 白像素过滤
    mask_not_white = ~((df['R'] >= white_thresh) &
                       (df['G'] >= white_thresh) &
                       (df['B'] >= white_thresh))
    df = df[mask_not_white]
    counts_filtered = counts[~mask_not_white]
    counts = counts[mask_not_white]

    df['Count'] = counts
    df['Percentage'] = (df['Count'] / (total_pixels - sum(counts_filtered)) * 100).round(2)
    df['Hex'] = df.apply(lambda x: '#{:02x}{:02x}{:02x}'.format(
                     int(x['R']), int(x['G']), int(x['B'])), axis=1)

    filtered_df = df[df['Percentage'] >= pct_threshold].sort_values('Count', ascending=False)
    # 创建图像显示
    fig = px.imshow(img_array)
    fig.update_layout(
        title=f"图片: {filename}",
        title_x=0.5,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=40, b=0),
        height=500
    )

    # 创建颜色表格
    if filtered_df.empty:
        table = html.Div("没有找到满足阈值的颜色", className="text-center")
        bar_chart = html.Div()
    else:
        # 创建数据表格 - 添加真实颜色示例列
        table = DataTable(
            id='color-table',
            columns=[
                {"name": "颜色示例", "id": "ColorSample", "presentation": "markdown"},
                {"name": "十六进制", "id": "Hex"},
                {"name": "RGB值", "id": "RGB"},
                {"name": "像素数量", "id": "Count", "type": "numeric", "format": {"specifier": ","}},
                {"name": "占比(%)", "id": "Percentage", "type": "numeric", "format": {"specifier": ".2f"}},
                {"name": "R", "id": "R"},      # 隐藏列，用于复制
                {"name": "G", "id": "G"},
                {"name": "B", "id": "B"}
            ],
            data=[
                {
                    "ColorSample": f"<div style='background-color: {row['Hex']}; width: 30px; height: 30px; border: 1px solid #000;'></div>",
                    "Hex": row['Hex'],
                    "RGB": f"({row['R']}, {row['G']}, {row['B']})",
                    "Count": row['Count'],
                    "Percentage": row['Percentage'],
                    "R": int(row['R']),
                    "G": int(row['G']),
                    "B": int(row['B'])
                }
                for _, row in filtered_df.iterrows()
            ],
            row_selectable='multi',
            selected_rows=[],           # 默认全不选
            hidden_columns=['R', 'G', 'B'],
            style_cell={'textAlign': 'center', 'padding': '10px', 'fontFamily': 'Arial, sans-serif'},
            style_header={'fontWeight': 'bold', 'backgroundColor': '#f8f9fa'},
            style_table={'overflowX': 'auto', 'boxShadow': '0 4px 6px rgba(0,0,0,0.1)'},
            markdown_options={"html": True},
            page_action='none',
            style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': 'rgb(248, 248, 248)'}]
        )
        
        # 创建颜色占比柱状图
        bar_fig = go.Figure()
        
        # 限制显示的颜色数量（最多20种）
        display_df = filtered_df.head(20)
        
        # 添加柱状图数据
        bar_fig.add_trace(go.Bar(
            x=display_df['Hex'],
            y=display_df['Percentage'],
            marker_color=display_df['Hex'],
            marker_line=dict(color='#000', width=1),
            text=display_df['Percentage'].apply(lambda x: f"{x:.2f}%"),
            textposition='outside',
            name='颜色占比'
        ))
        
        # 更新布局
        bar_fig.update_layout(
            title='颜色占比分析',
            xaxis_title='颜色',
            yaxis_title='占比(%)',
            showlegend=False,
            margin=dict(l=40, r=40, t=60, b=100),
            height=400,
            xaxis_tickangle=-45
        )
        
        # 创建图表组件
        bar_chart = dcc.Graph(
            id='color-bar-chart',
            figure=bar_fig,
            config={'displayModeBar': True}
        )

    return fig, table, bar_chart, ''  # 重置粘贴存储

# 处理粘贴事件
app.clientside_callback(
    """
    function setupPasteHandler() {
        document.addEventListener('paste', function(e) {
            const items = e.clipboardData.items;
            for (const item of items) {
                if (item.type.indexOf('image') !== -1) {
                    const blob = item.getAsFile();
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        const contents = event.target.result;
                        // 触发存储更新 - 存储为字符串而不是字典
                        dash_clientside.set_props('pasted-image-store', {'data': contents});
                    };
                    reader.readAsDataURL(blob);
                    e.preventDefault();
                    break;
                }
            }
        });
        return '粘贴功能已启用';
    }
    """,
    Output('paste-area', 'children'),
    Input('paste-area', 'n_clicks')
)

# 修复并增强复制功能（添加十六进制格式）
app.clientside_callback(
    """
    function(n_clicks, selected_rows, data, fmt) {
        if (n_clicks === 0 || !selected_rows || !data) {
            return '';
        }
        
        // 确保selected_rows是数组且不为空
        if (!Array.isArray(selected_rows) || selected_rows.length === 0) {
            return '请先选择颜色';
        }
        
        let items = [];
        for (let i = 0; i < selected_rows.length; i++) {
            const rowIndex = selected_rows[i];
            if (rowIndex >= 0 && rowIndex < data.length) {
                const row = data[rowIndex];
                if (row) {
                    items.push(row);
                }
            }
        }
        
        if (items.length === 0) {
            return '没有有效的颜色数据';
        }
        
        let text = '';
        if (fmt === 'hex') {
            // 十六进制格式
            const hexValues = items.map(item => item.Hex);
            text = hexValues.join(', ');
        } else if (fmt === 'py') {
            // Python list格式 (RGB)
            const colors = items.map(item => [item.R, item.G, item.B]);
            text = '[' + colors.map(c => `[${c.join(',')}]`).join(', ') + ']';
        } else if (fmt === 'r') {
            // R向量格式 (RGB)
            const colors = items.map(item => [item.R, item.G, item.B]);
            const inner = colors.map(c => `c(${c.join(',')})`).join(',');
            text = `c(${inner})`;
        } else {
            return '未知的复制格式';
        }
        
        // 复制到剪贴板
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        
        return '已复制 ' + items.length + ' 种颜色 (' + fmt + ')';
    }
    """,
    Output('copy-status', 'children'),
    Input('copy-btn', 'n_clicks'),
    State('color-table', 'selected_rows'),
    State('color-table', 'data'),
    State('copy-format', 'value')
)

# 添加全局样式
app.clientside_callback(
    """
    function addGlobalStyles() {
        const style = document.createElement('style');
        style.innerHTML = `
            .dash-table-container .dash-spreadsheet-container {
                border: 1px solid #dee2e6;
                border-radius: 5px;
            }
            .dash-table-tooltip {
                max-width: 300px;
                white-space: normal;
            }
            .copy-btn {
                transition: all 0.3s;
            }
            .copy-btn:hover {
                transform: scale(1.05);
                box-shadow: 0 0 5px rgba(0,0,0,0.2);
            }
            #color-bar-chart {
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 15px;
                background: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .copy-format-dropdown .Select-control {
                min-height: 38px;
            }
        `;
        document.head.appendChild(style);
        return '';
    }
    """,
    Output('dummy-output', 'children'),
    Input('dummy-output', 'n_clicks')
)

if __name__ == '__main__':
    app.run(debug=True)
