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

# 初始化Dash应用
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
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
            html.Label("像素数量阈值 (只显示超过此数量的颜色):"),
            dcc.Slider(
                id='threshold-slider',
                min=0,
                max=100,
                step=1,
                value=36,
                marks={i: str(i) for i in range(0, 101, 10)}
            )
        ], width=8)
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
            html.Div(id='dummy-output', style={'display': 'none'})
        ], width=10)
    ], justify="center")
], fluid=True)

# 处理图像上传和粘贴
@app.callback(
    Output('display-image', 'figure'),
    Output('color-table-container', 'children'),
    Output('color-chart-container', 'children'),
    Input('upload-image', 'contents'),
    Input('threshold-slider', 'value'),
    State('upload-image', 'filename'),
    prevent_initial_call=True
)
def process_image(contents, threshold, filename):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if not contents:
        return no_update, no_update, no_update

    # 从base64编码中提取图像数据
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        image = Image.open(io.BytesIO(decoded))
    except Exception as e:
        return no_update, html.Div(f"错误: {str(e)}", className="text-danger"), no_update

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
    df['Count'] = counts
    df['Percentage'] = (df['Count'] / total_pixels * 100).round(2)
    df['Hex'] = df.apply(lambda x: '#{:02x}{:02x}{:02x}'.format(
                     int(x['R']), int(x['G']), int(x['B'])), axis=1)
    # 应用阈值过滤
    filtered_df = df[df['Count'] >= threshold].sort_values('Count', ascending=False)

    # 创建图像显示
    fig = px.imshow(img_array)
    fig.update_layout(
        title=f"上传的图片: {filename}",
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
                {"name": "操作", "id": "Actions", "presentation": "markdown"}
            ],
            data=[
                {
                    "ColorSample": f"<div style='background-color: {row['Hex']}; width: 30px; height: 30px; border: 1px solid #000;'></div>",
                    "Hex": row['Hex'],
                    "RGB": f"({row['R']}, {row['G']}, {row['B']})",
                    "Count": row['Count'],
                    "Percentage": row['Percentage'],
                    "Actions": f"<button class='btn btn-sm btn-outline-secondary' onclick=\"navigator.clipboard.writeText('{row['Hex']}');\">复制</button>"
                }
                for _, row in filtered_df.iterrows()
            ],
            style_cell={
                'textAlign': 'center',
                'padding': '10px',
                'fontFamily': 'Arial, sans-serif'
            },
            style_header={
                'fontWeight': 'bold',
                'backgroundColor': '#f8f9fa',
                'border': '1px solid #dee2e6'
            },
            style_data={
                'border': '1px solid #dee2e6'
            },
            style_table={
                'overflowX': 'auto',
                'boxShadow': '0 4px 6px rgba(0,0,0,0.1)',
                'borderRadius': '5px'
            },
            markdown_options={"html": True},
            page_action='none',
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': 'rgb(248, 248, 248)'
                }
            ]
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

    return fig, table, bar_chart

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
                        // 触发上传组件更新
                        document.getElementById('upload-image').dispatchEvent(
                            new CustomEvent('dash_upload', {detail: {
                                files: [new File([blob], 'pasted-image.png')],
                                content: contents
                            }})
                        );
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
