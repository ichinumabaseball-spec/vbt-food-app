import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import io
import json
from datetime import datetime

# --- 1. 初期設定と認証 ---
st.set_page_config(page_title="VBT Food Log", page_icon="🍱")

try:
    # SupabaseとGeminiの準備
    supabase: Client = create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"]
    )
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
except Exception as e:
    st.error(f"❌ 設定エラー: secrets.tomlを確認してください。\n{e}")
    st.stop()

# --- 2. ユーザーIDの取得 (GAS連携用) ---
query_params = st.query_params
user_id = query_params.get("uid", "TEST_USER")

st.title(f"🍱 食事記録 AI解析")
st.caption(f"記録ユーザー: {user_id}")

# --- 3. カメラ撮影 ---
uploaded_file = st.camera_input("食事を撮影してください")

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="撮影した画像", use_container_width=True)
    
    # 「解析して保存」ボタン
    if st.button("🚀 AI解析して保存する", type="primary"):
        with st.spinner("🤖 AIが画像を解析中..."):
            try:
                # --- A. Geminiで画像解析 ---
                
                # ★修正ポイント: リストにあった「安定版Flash」を使います
                target_model = 'models/gemini-flash-latest'
                
                try:
                    model = genai.GenerativeModel(target_model)
                    
                    # AIへの命令文
                    prompt = """
                    この食事画像を解析し、以下の情報をJSON形式で出力してください。
                    JSONのキーは必ず以下にしてください:
                    - menu_name (料理名:日本語)
                    - kcal (カロリー:数値)
                    - p (タンパク質g:数値)
                    - f (脂質g:数値)
                    - c (炭水化物g:数値)
                    ※数値は推定で構いません。JSON以外の文字は出力しないでください。
                    """
                    
                    response = model.generate_content([prompt, image])
                    
                    # 結果(文字列)をJSONデータに変換
                    json_text = response.text.replace("```json", "").replace("```", "").strip()
                    food_data = json.loads(json_text)
                    
                    st.success("✅ 解析完了！")
                    st.write(food_data) 

                    # --- B. Supabase保存 (解析成功時のみ実行) ---
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='JPEG')
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_path = f"{user_id}/{timestamp}.jpg"
                    
                    st.write("📤 画像を保存中...")
                    supabase.storage.from_("food_images").upload(
                        file_path,
                        img_byte_arr,
                        {"content-type": "image/jpeg"}
                    )
                    
                    public_url_data = supabase.storage.from_("food_images").get_public_url(file_path)
                    image_url = public_url_data

                    st.write("💾 データを記録中...")
                    insert_data = {
                        "user_id": user_id,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "meal_type": "未設定",
                        "menu_name": food_data.get("menu_name"),
                        "macros": food_data,
                        "image_url": image_url,
                        "created_at": datetime.now().isoformat()
                    }
                    supabase.table("food_logs").insert(insert_data).execute()
                    st.success("🎉 保存完了しました！")

                except Exception as api_error:
                    st.error(f"❌ AI解析エラー: {api_error}")
                
            except Exception as e:
                st.error(f"予期せぬエラー: {e}")