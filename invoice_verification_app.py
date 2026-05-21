import streamlit as st
import pandas as pd
import pdfplumber
from anthropic import Anthropic
import io
import json
from datetime import datetime

# ページ設定
st.set_page_config(
    page_title="PDF請求書検証システム",
    page_icon="📋",
    layout="wide"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# タイトル
st.markdown('<div class="main-header">📋 PDF請求書検証システム</div>', unsafe_allow_html=True)
st.markdown("---")

# セッション状態の初期化
if 'verification_result' not in st.session_state:
    st.session_state.verification_result = None
if 'verification_history' not in st.session_state:
    st.session_state.verification_history = []

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")
    
    # API Key入力
    api_key = st.text_input(
        "Claude API Key",
        type="password",
        help="Anthropic API Keyを入力してください"
    )
    
    st.markdown("---")
    
    # 検証オプション
    st.subheader("検証オプション")
    check_amount = st.checkbox("金額の妥当性確認", value=True)
    check_tariff = st.checkbox("TARIFF料金照合", value=True)
    check_calculation = st.checkbox("計算の正確性確認", value=True)
    check_format = st.checkbox("請求書フォーマット確認", value=True)
    
    st.markdown("---")
    
    # 使い方
    st.subheader("📖 使い方")
    st.markdown("""
    1. **PDF請求書**をアップロード
    2. **Excel入力データ**をアップロード
    3. **TARIFF情報**をアップロード（任意）
    4. **検証開始**ボタンをクリック
    5. 結果を確認
    """)
    
    st.markdown("---")
    
    # 検証履歴
    if st.session_state.verification_history:
        st.subheader("📊 検証履歴")
        st.write(f"総検証回数: {len(st.session_state.verification_history)}")

# メインエリア
tab1, tab2, tab3 = st.tabs(["📤 ファイルアップロード", "📊 検証結果", "📚 履歴"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 ファイル選択")
        
        # PDF請求書
        pdf_file = st.file_uploader(
            "PDF請求書",
            type=['pdf'],
            help="検証対象のPDF請求書をアップロードしてください"
        )
        
        # Excel入力データ
        excel_file = st.file_uploader(
            "Excel入力データ",
            type=['xlsx', 'xls'],
            help="請求書の入力データが含まれるExcelファイル"
        )
        
        # TARIFF情報（任意）
        tariff_file = st.file_uploader(
            "TARIFF情報（任意）",
            type=['xlsx', 'xls'],
            help="料金表・TARIFF情報のExcelファイル"
        )
    
    with col2:
        st.subheader("📋 アップロード状況")
        
        upload_status = []
        
        if pdf_file:
            st.success(f"✓ PDF請求書: {pdf_file.name}")
            upload_status.append("PDF")
        else:
            st.info("⏳ PDF請求書: 未アップロード")
        
        if excel_file:
            st.success(f"✓ Excel入力データ: {excel_file.name}")
            upload_status.append("Excel")
        else:
            st.info("⏳ Excel入力データ: 未アップロード")
        
        if tariff_file:
            st.success(f"✓ TARIFF情報: {tariff_file.name}")
            upload_status.append("TARIFF")
        else:
            st.info("ℹ️ TARIFF情報: 任意（未アップロード）")
        
        # プログレスバー
        progress = len(upload_status) / 2  # PDF + Excel が必須
        st.progress(progress)
        
        if progress >= 1.0:
            st.success("✓ 必須ファイルの準備完了")

# PDF読取関数
def extract_pdf_content(pdf_file):
    """PDFからテキストと表を抽出"""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            text_content = ""
            tables = []
            
            for page_num, page in enumerate(pdf.pages):
                # テキスト抽出
                text_content += f"\n--- Page {page_num + 1} ---\n"
                text_content += page.extract_text() or ""
                
                # 表抽出
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
            
            return {
                'text': text_content,
                'tables': tables,
                'page_count': len(pdf.pages)
            }
    except Exception as e:
        st.error(f"PDF読取エラー: {str(e)}")
        return None

# Excel読取関数
def read_excel_data(excel_file):
    """Excelファイルを読み込む"""
    try:
        df = pd.read_excel(excel_file)
        return df
    except Exception as e:
        st.error(f"Excel読取エラー: {str(e)}")
        return None

# 検証関数
def verify_invoice(pdf_content, excel_data, tariff_data, api_key, options):
    """Claude APIを使用して請求書を検証"""
    try:
        client = Anthropic(api_key=api_key)
        
        # プロンプト構築
        prompt = f"""
あなたは請求書検証の専門家です。以下の情報を使用して、PDF請求書の内容が正確かどうかを詳細に検証してください。

【PDF請求書の内容】
{pdf_content['text']}

【PDF内の表データ】
{json.dumps(pdf_content['tables'], ensure_ascii=False, indent=2)}

【Excel入力データ】
{excel_data.to_string()}

【TARIFF情報】
{tariff_data.to_string() if tariff_data is not None else "TARIFF情報は提供されていません"}

【検証項目】
"""
        
        if options['check_amount']:
            prompt += "\n✓ 金額の妥当性（異常な金額、桁違い等）"
        if options['check_tariff']:
            prompt += "\n✓ TARIFF料金との照合"
        if options['check_calculation']:
            prompt += "\n✓ 計算の正確性（合計、税金計算等）"
        if options['check_format']:
            prompt += "\n✓ 請求書フォーマットの妥当性"
        
        prompt += """

以下の形式で検証結果を出力してください：

# 検証結果サマリー

## 総合評価
- **判定**: ✓ 合格 / ⚠ 要確認 / ✗ 不合格
- **信頼度**: XX%
- **検出された問題**: X件

## 検証スコア
- 金額の妥当性: XX/100点
- 計算の正確性: XX/100点
- フォーマット: XX/100点
- TARIFF照合: XX/100点

---

# 詳細検証結果

## ✓ 一致項目
[項目名]
- PDF値: [値]
- Excel値: [値]
- 状態: 一致

## ⚠ 要確認項目
[項目名]
- PDF値: [値]
- Excel値: [値]
- 差異: [差異の説明]
- 影響度: 高/中/低

## ✗ 不一致項目
[項目名]
- PDF値: [値]
- Excel値: [値]
- 差異金額: XXX円
- 原因推定: [推定される原因]

---

# 計算検証

## 小計・合計の確認
- 明細合計: XXX円
- 計算結果: XXX円
- 差異: XXX円

## 税金計算
- 税抜金額: XXX円
- 税率: XX%
- 消費税: XXX円（計算値: XXX円）
- 差異: XXX円

---

# TARIFF照合結果
[各項目のTARIFF料金との比較]

---

# 推奨アクション

## 優先度：高
1. [具体的な修正提案]

## 優先度：中
1. [確認が必要な項目]

## 優先度：低
1. [軽微な指摘事項]

---

# 備考・補足
[その他気づいた点や注意事項]
"""
        
        # Claude APIコール
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return message.content[0].text
        
    except Exception as e:
        st.error(f"検証エラー: {str(e)}")
        return None

# 検証実行ボタン
with tab1:
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        verify_button = st.button(
            "🔍 検証開始",
            type="primary",
            use_container_width=True,
            disabled=not (pdf_file and excel_file and api_key)
        )

# 検証処理
if verify_button:
    if not api_key:
        st.error("⚠️ Claude API Keyを入力してください")
    elif not pdf_file or not excel_file:
        st.error("⚠️ PDF請求書とExcel入力データをアップロードしてください")
    else:
        with st.spinner("🔄 検証中... しばらくお待ちください"):
            try:
                # ファイル読込
                pdf_content = extract_pdf_content(pdf_file)
                excel_data = read_excel_data(excel_file)
                tariff_data = read_excel_data(tariff_file) if tariff_file else None
                
                if pdf_content and excel_data is not None:
                    # 検証オプション
                    options = {
                        'check_amount': check_amount,
                        'check_tariff': check_tariff,
                        'check_calculation': check_calculation,
                        'check_format': check_format
                    }
                    
                    # 検証実行
                    result = verify_invoice(
                        pdf_content,
                        excel_data,
                        tariff_data,
                        api_key,
                        options
                    )
                    
                    if result:
                        # 結果を保存
                        st.session_state.verification_result = {
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'pdf_name': pdf_file.name,
                            'excel_name': excel_file.name,
                            'result': result
                        }
                        
                        # 履歴に追加
                        st.session_state.verification_history.append(
                            st.session_state.verification_result
                        )
                        
                        st.success("✅ 検証が完了しました！「検証結果」タブで確認してください。")
                        st.balloons()
                
            except Exception as e:
                st.error(f"❌ エラーが発生しました: {str(e)}")

# 検証結果タブ
with tab2:
    if st.session_state.verification_result:
        result_data = st.session_state.verification_result
        
        # ヘッダー情報
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("検証日時", result_data['timestamp'])
        with col2:
            st.metric("PDF請求書", result_data['pdf_name'])
        with col3:
            st.metric("入力データ", result_data['excel_name'])
        
        st.markdown("---")
        
        # 検証結果表示
        st.markdown(result_data['result'])
        
        # ダウンロードボタン
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            st.download_button(
                label="📥 結果をテキストでダウンロード",
                data=result_data['result'],
                file_name=f"verification_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        with col2:
            # JSON形式でダウンロード
            json_data = json.dumps(result_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 結果をJSONでダウンロード",
                data=json_data,
                file_name=f"verification_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col3:
            if st.button("🗑️ 結果をクリア", use_container_width=True):
                st.session_state.verification_result = None
                st.rerun()
    else:
        st.info("ℹ️ 検証を実行すると、ここに結果が表示されます。")
        st.markdown("「ファイルアップロード」タブからファイルをアップロードして検証を開始してください。")

# 履歴タブ
with tab3:
    if st.session_state.verification_history:
        st.subheader(f"📊 検証履歴（{len(st.session_state.verification_history)}件）")
        
        for idx, history in enumerate(reversed(st.session_state.verification_history)):
            with st.expander(f"#{len(st.session_state.verification_history) - idx} - {history['timestamp']} - {history['pdf_name']}"):
                st.markdown(f"**PDF請求書**: {history['pdf_name']}")
                st.markdown(f"**入力データ**: {history['excel_name']}")
                st.markdown("---")
                st.markdown(history['result'])
        
        st.markdown("---")
        if st.button("🗑️ 履歴をすべてクリア"):
            st.session_state.verification_history = []
            st.rerun()
    else:
        st.info("ℹ️ 検証履歴がありません。")

# フッター
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>© 2026 PDF請求書検証システム | Powered by Claude AI</p>
</div>
""", unsafe_allow_html=True)
