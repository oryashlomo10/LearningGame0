import streamlit as st

st.set_page_config(page_title="Conquest", page_icon="🏰", layout="centered")

# Right-to-left layout for Hebrew
st.markdown(
    """
    <style>
    .stApp { direction: rtl; text-align: right; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏰 Conquest")
st.subheader("Learn. Compete. Conquer.")

st.write(
    """
    **Conquest** הוא משחק אסטרטגיה תחרותי ללמידה.

    סטודנטים מצטרפים לקבוצת לימוד של קורס, מעלים חומרי לימוד,
    ומערכת AI מייצרת מהם שאלות ברמות קושי שונות.
    כדי לכבוש שטחים על המפה המשותפת, צריך לענות נכון על השאלות –
    וכך לומדים ומתחרים בו זמנית.
    """
)

st.info("האפליקציה בשלבי פיתוח ראשוניים. בקרוב: העלאת חומרי לימוד, שאלות ומפת משחק.")
