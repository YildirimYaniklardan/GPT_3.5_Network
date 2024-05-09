import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import openai
import uuid

# MongoDB Bağlantısı
client = MongoClient("YOUR_MONGODB")
db = client.user_database
sessions = db.sessions

# OpenAI API key
openai.api_key = 'YOUR_OPENAI_API_KEY'

# Tema Renkleri
primary_color = "#34d2eb"  # Ana renk (mavi tonu)
secondary_background_color = "#f0f2f6"  # Arka planın ikincil rengi (açık gri tonu)
text_color = "#333333"  # Metin rengi (koyu gri tonu)
button_color = "#009688"  # Buton rengi (yeşil tonu)

# Streamlit Teması ve Görsel İyileştirmeler
st.markdown(
    """
    <style>
        .reportview-container .main .block-container{{
            max-width: 900px;
            padding-top: 2rem;
            padding-right: 2rem;
            padding-left: 2rem;
            padding-bottom: 3rem;
            background-color: {secondary_background_color};
            color: {text_color};
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        .sidebar .sidebar-content{{
            background-color: {primary_color};
            color: white;
        }}
        .sidebar .sidebar-content .block-container{{
            padding: 1rem;
        }}
        .css-hby737, .stTextInput>div>div>input, .stTextArea>div>textarea{{
            color: {text_color};
            background-color: white;
        }}
        .stTextInput>div>div>input:focus, .stTextArea>div>textarea:focus{{
            border-color: {primary_color};
        }}
        .stButton>button{{
            background-color: {button_color};
            color: white;
            border-radius: 20px;
            border: none;
            box-shadow: 0 0 4px #999;
            transition: box-shadow 0.2s, background-color 0.2s;
        }}
        .stButton>button:hover{{
            background-color: #00796b; /* Darken button color on hover */
        }}
    </style>
    """.format(primary_color=primary_color, secondary_background_color=secondary_background_color, text_color=text_color, button_color=button_color),
    unsafe_allow_html=True
)

def register_user(username, password):
    users = db.users
    if users.find_one({"username": username}):
        return False
    users.insert_one({"username": username, "password": password})
    return True

def check_login(username, password):
    users = db.users
    user = users.find_one({"username": username, "password": password})
    return user is not None

def get_last_session(username):
    last_session = sessions.find_one({"username": username}, sort=[("created_at", -1)])
    return last_session['session_id'] if last_session else create_new_session(username)

def create_new_session(username):
    session_id = str(uuid.uuid4())
    sessions.insert_one({
        "username": username,
        "session_id": session_id,
        "interactions": [],
        "created_at": datetime.now()
    })
    return session_id

def add_interaction_to_session(session_id, question, answer):
    sessions.update_one(
        {"session_id": session_id},
        {"$push": {"interactions": {"question": question, "answer": answer, "timestamp": datetime.now()}}}
    )

def ask_question(question_text, session_id):
    session_data = sessions.find_one({"session_id": session_id})
    interactions = session_data["interactions"]

    messages = [{'role': 'system', 'content': 'You are a helpful assistant.'}]
    for interaction in interactions:
        messages.append({'role': 'user', 'content': interaction['question']})
        messages.append({'role': 'assistant', 'content': interaction['answer']})

    messages.append({'role': 'user', 'content': question_text})

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    answer = response['choices'][0]['message']['content'].strip()

    add_interaction_to_session(session_id, question_text, answer)
    return answer

def get_sessions(username):
    user_sessions = sessions.find({"username": username}).sort("created_at", -1)
    return list(user_sessions)

def display_session_interactions(session_id):
    session_data = sessions.find_one({"session_id": session_id})
    if session_data:
        for interaction in session_data["interactions"]:
            st.markdown(f"**Soru:** {interaction['question']}")
            st.markdown(f"**Cevap:** {interaction['answer']}")
            st.markdown("---")

def display_login_form():
    with login_container:
        with st.form("login_form"):
            username = st.text_input("Kullanıcı Adı")
            password = st.text_input("Şifre", type="password")
            login_button = st.form_submit_button("Giriş Yap")
            register_button = st.form_submit_button("Kayıt Ol")

        if login_button:
            if check_login(username, password):
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.session_state['session_id'] = get_last_session(username)
                login_container.empty()
            else:
                st.error("Giriş başarısız. Lütfen bilgilerinizi kontrol edin.")

        if register_button:
            if register_user(username, password):
                st.success("Kayıt başarılı. Şimdi giriş yapabilirsiniz.")
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.session_state['session_id'] = create_new_session(username)
                login_container.empty()
            else:
                st.error("Kullanıcı adı zaten kullanımda.")


# Logout Fonksiyonu
def logout():
    st.session_state['logged_in'] = False
    st.session_state['username'] = None
    st.session_state['session_id'] = None
    login_container.empty()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['session_id'] = None

login_container = st.empty()
if not st.session_state['logged_in']:
    display_login_form()

if st.session_state['logged_in']:
    if st.sidebar.button('Çıkış Yap'):
        logout()
        st.success("Başarıyla çıkış yaptınız.")
    user_sessions = get_sessions(st.session_state['username'])
    with st.sidebar:
        st.header("Sohbetler")
        for session in user_sessions:
            first_question = session["interactions"][0]["question"] if session["interactions"] else "New session"
            if st.button(f"{first_question[:50]}...", key=session["session_id"]):
                st.session_state['session_id'] = session["session_id"]
        if st.button("New Chat"):
            st.session_state['session_id'] = create_new_session(st.session_state['username'])

    if st.session_state['session_id']:
        interaction_container = st.container()  # Soru-cevapları bu konteynerde göster
        question_container = st.container()  # Soru girişi için ayrı bir konteyner

        with interaction_container:
            display_session_interactions(st.session_state['session_id'])

        with question_container:
            question = st.text_input("Sorunuzu yazın:", key="question_input")
            if st.button("Soru Sor", key="ask_question"):
                answer = ask_question(question, st.session_state['session_id'])
                st.experimental_rerun()  # Sayfayı yeniden yükle
                interaction_container.empty()  # Yeni cevap eklendikten sonra interaksiyonları yeniden yükle
                display_session_interactions(st.session_state['session_id'])
                st.markdown(f"**Cevap:** {answer}")