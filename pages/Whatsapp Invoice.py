
import streamlit as st
import pandas as pd
import os
from pathlib import Path
import openpyxl
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep
from plyer import notification

st.set_page_config(page_title='Science Matters')
st.title('Science Matters')
st.subheader('Choose an action')

#driver = webdriver.Chrome()
#driver = webdriver.Chrome(ChromeDriverManager().install())
def messenger(driver, m_url, f_path,content):
    try:
        #driver = webdriver.Chrome(executable_path=ChromeDriverManager().install(), options=options)
        driver.get(m_url)
        #driver.get("https://www.google.com")
        sleep(7)
        msg_box = driver.find_element(By.XPATH, '//div[@title = "Type a message"]')
        msg_box.send_keys(content)
        sleep(1)

        send_button = driver.find_element(By.XPATH, '//span[@data-icon="send"]')
        send_button.click()
        sleep(3)
        #attachments
        attachment_box = driver.find_element(By.XPATH, '//div[@title = "Attach"]')
        attachment_box.click()

        # attachment path
        attach = driver.find_element(By.XPATH, '//input[@accept="*"]')
        attach.send_keys(f_path)

        sleep(3)

        send_button = driver.find_element(By.XPATH, '//span[@data-icon="send"]')
        send_button.click()

        sleep(3)
    except Exception as e:
        notification.notify(
            title="Whatsapp message not sent",
            message="Error while sending!",
            #app_icon=r"<Your icon file>",
            app_name="Whatsapp Message error",
            toast=True,
        )
        print(e)
        os._exit(0)

def send_txt(driver, message_content):

    msg_box = driver.find_element(By.XPATH, '//div[@title = "Type a message"]')
    msg_box.send_keys(message_content)
    sleep(1)

    send_button = driver.find_element(By.XPATH, '//span[@data-icon="send"]')
    send_button.click()
    sleep(3)

##################retrieve info from excel ***************************


# Path Setting:
try:
    current_path = Path(__file__).parent.absolute()  # Get the file path for this py file
except:
    current_path = (Path.cwd())

# import the inv_sheet from the excel file
filepath = os.path.join(current_path, 'ERP.xlsx')
wb = openpyxl.load_workbook(filepath)
inv_ws = wb['Invoice']
df = pd.read_excel(filepath, engine='openpyxl', sheet_name='Invoice')
parent_df = pd.read_excel(filepath, engine='openpyxl', sheet_name='Parent')
not_sent_df = df.loc[df['whatsapp'] == 'no']
st.dataframe(not_sent_df)
###################create GUI##################

url1 = "https://web.whatsapp.com/send?phone=+65"
if st.button("Send all invoices via whatsapp"):
    l_inv = not_sent_df['inv_no'].values.tolist()
    path = r"C:\Users\Choon Yong Chong\OneDrive\Documents\Business\chromedriver.exe"
    options = webdriver.ChromeOptions()
    options.add_argument('--profile-directory=Profile 1')
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    #options.add_argument(r"user-data-dir=C:\Users\Choon Yong Chong\AppData\Local\Google\Chrome\User Data")
    options.add_argument(r"user-data-dir=C:\Users\Choon Yong Chong\Documents\Business")
    x_driver = webdriver.Chrome(executable_path=path, options=options)
    for i in l_inv:
        try:
            x_acct = not_sent_df.loc[not_sent_df['inv_no'] == i, 'acct_no'].iloc[0]
            x_tel = parent_df.loc[parent_df['acct_no'] == x_acct, 'phone'].iloc[0]
            pname = parent_df.loc[parent_df['acct_no'] == x_acct, 'p_name'].iloc[0]
            name_text = parent_df.loc[parent_df['acct_no'] == x_acct, 'stud_name'].iloc[0]
            frm_mth = not_sent_df.loc[not_sent_df['inv_no'] == i, 'inv_frmdt'].iloc[0]
            to_mth = not_sent_df.loc[not_sent_df['inv_no'] == i, 'inv_todt'].iloc[0]
            due_dt = not_sent_df.loc[not_sent_df['inv_no'] == i, 'due_dt'].iloc[0]
            inv_amt = not_sent_df.loc[not_sent_df['inv_no'] == i, 'amt'].iloc[0]
            #messenger()
            url2 = url1 + str(x_tel)
            pdfpath = os.path.join(current_path, 'Invoice pdf\\' + str(i) + ".pdf")
            text = f"Hi {pname}, the fee for {name_text} from {frm_mth} to {to_mth} is ${inv_amt} due on {due_dt} as per attached invoice. Please transfer the fee to me via PayNow (UEN 202238718D, not phone number) or bank transfer and let me know so I may acknowledge receipt. Thank you."
            messenger(x_driver, url2, pdfpath,text)
            for row in inv_ws.iter_rows():
                if str(row[1].value) == str(i):
                    row[8].value = 'sent'
        except Exception as e:
            st.write(e)
    wb.save(filepath)
    wb.close()
with st.form("Send selected invoices"):
    p_inv = st.text_input("Invoice number. Use \',\' for more than one invoice.")
    submitted = st.form_submit_button("Send")
    if submitted:
        l_inv2 = p_inv.split(",")
        for i in l_inv2:
            st.write(i)
            try:
                #messenger()
                pdfpath = os.path.join(current_path, 'Invoice pdf\\' + i + ".pdf")
                messenger(pdfpath)
            except:
                st.write("sent failed!")



