def search_donor_name(search_string, search_body):

    body_list = search_body.split('___')
    a_list = []
    for i in range(len(body_list)):
        if body_list[i] == search_string:
            a_list = []
            a_list = body_list[i+1]
            for i in a_list.split('__'):
                return (i.replace('_', ' '))

def search_donor_email(search_string, search_body):

    body_list = search_body.split('___')
    a_list = []
    for i in range(len(body_list)):
        if body_list[i] == search_string:
            a_list = []
            a_list = body_list[i+2]
            for i in a_list.split('__'):
                return i
def search_donor_adress(search_string, search_body):
    address_1 = ''
    address_2 = ''
    address_3 = ''
    body_list = search_body.split('___')
    a_list = []
    for i in range(len(body_list)):
        if body_list[i] == search_string:
            a_list = []
            b_list = []
            a_list = body_list[i+3]
            b_list = body_list[i+4]
            c_list = body_list[i+5]
            for p in a_list.split('__'):
                address_1 = p
            for k in b_list.split('__'):
                address_2 += k
            for j in c_list.split('__'):
                address_3 += j
            return address_1 + '' + address_2 + '' + address_3.replace('Donor_Phone_Number', '')
def search_donor_number(search_string, search_body):

    body_list = search_body.split('___')
    a_list = []
    for i in range(len(body_list)):
        if body_list[i] == search_string:
            a_list = []
            a_list = body_list[i+6]
            for i in a_list.split('__'):
                return (i)
def search_donor_additional(search_string, search_body):
    additional_1 = ''
    additional_2 = ''
    body_list = search_body.split('___')
    a_list = []
    for i in range(len(body_list)):
        if body_list[i] == search_string:
            a_list = []
            a_list = body_list[i+7]
            b_list = body_list[i+8]
            for j in a_list.split('__'):
                print(j)
                additional_1 += j
            for k in b_list.split('__'):
                print(k)
                additional_2 += k
            return additional_1 + additional_2
#this is a python email reader

#importing neccesary modules
import imaplib
import email
from email.header import decode_header
import os
import csv

#account credentials
username = "samarth.sridhara@gmail.com" ##Put your gmail account name here
password = "samsri477"

#num of top emails to read
N= 1

#field names
fields = ['Subject', 'From', 'Donor Name', 'Donor Email', 'Donor Address', 'Donor Number', 'Donor Additional','Body']

#data rows
rows = []
def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)

#connect to IMAP Server

# create an IMAP4 class with SSL
imap = imaplib.IMAP4_SSL("imap.gmail.com")
# authenticate
imap.login(username, password)

status, messages = imap.select("INBOX")

messages = int(messages[0])

for i in range(messages, messages-N, -1):
    # fetch the email message by ID
    res, msg = imap.fetch(str(i), "(RFC822)")
    for response in msg:
        if isinstance(response, tuple):
            # parse a bytes email into a message object
            msg = email.message_from_bytes(response[1])
            # decode the email subject
            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                # if it's a bytes, decode to str
                subject = subject.decode(encoding)
            # decode email sender
            From, encoding = decode_header(msg.get("From"))[0]
            if isinstance(From, bytes):
                From = From.decode(encoding)
            print("Subject:", subject)
            rows.append(subject)
            print("From:", From)
            rows.append(From)
            # if the email message is multipart
            if msg.is_multipart():
                # iterate over email parts
                for part in msg.walk():
                    # extract content type of email
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    try:
                        # get the email body
                        body = part.get_payload(decode=True).decode()
                    except:
                        pass
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        # print text/plain emails and skip attachments
                        print(body)
                        donor_name = search_donor_name('Donor_Name', clean(body))
                        rows.append(donor_name)
                        donor_email = search_donor_email('Donor_Name', clean(body))
                        rows.append(donor_email)
                        donor_adress = search_donor_adress('Donor_Name', clean(body))
                        rows.append(donor_adress)
                        donor_number = search_donor_number('Donor_Name', clean(body))
                        rows.append(donor_number)
                        donor_additional = search_donor_additional('Donor_Name', clean(body))
                        rows.append(donor_additional)
                        rows.append(clean(body))
                    elif "attachment" in content_disposition:
                        # download attachment
                        filename = part.get_filename()
                        if filename:
                            folder_name = clean(subject)
                            if not os.path.isdir(folder_name):
                                # make a folder for this email (named after the subject)
                                os.mkdir(folder_name)
                            filepath = os.path.join(folder_name, filename)
                            # download attachment and save it
                            open(filepath, "wb").write(part.get_payload(decode=True))
            else:
                # extract content type of email
                content_type = msg.get_content_type()
                # get the email body
                body = msg.get_payload(decode=True).decode()
                #rows.append(body)
                if content_type == "text/plain":
                    # print only text email parts
                    donor_name = search_donor_name('Donor_Name', clean(body))
                    rows.append(donor_name)
                    donor_email = search_donor_email('Donor_Name', clean(body))
                    rows.append(donor_email)
                    donor_adress = search_donor_adress('Donor_Name', clean(body))
                    rows.append(donor_adress)
                    donor_number = search_donor_number('Donor_Name', clean(body))
                    rows.append(donor_number)
                    donor_additional = search_donor_additional('Donor_Name', clean(body))
                    rows.append(donor_additional)
                    print(body)
                    rows.append(clean(body))
            print("="*100)
# close the connection and logout
imap.close()
imap.logout()

filename = 'email_data.csv'



outer = []
inner = []
counter = 0
for i in range(0, len(rows)):

    counter += 1
    inner.append(rows[i])
    if counter == 8:
        counter = 0
        outer.append(list(inner))
        with open(filename, 'w') as csvfile:
            csvwriter = csv.writer(csvfile)

            csvwriter.writerow(fields)

            csvwriter.writerows(outer)
        inner.clear()

a = 'Great_job_i_getting_the_python_script_sorted_out_for_email_parsing___Can_you_please_take_this_email_as_a_example_and_extract_the_attributes_that__are_there_under__Donation_received___section_____Regards___Chakra_______________Forwarded_message____________From__Squarespace__no_reply_squarespace_com___Date__Tue__Jan_4__2022_at_1_35_PM__Subject__LaTrisha_Vetaw_for_Minneapolis_Ward_4_Has_Received_a_Contribution__To___chakra17_san_gmail_com____________image__Squarespace____http___sg_links_squarespace_com_ls_click_upn_anL_2FE0qPuv5EOFctfHcdiDx9zoX7rQG4mQFjQobgOjl6v3dH_2BqsY_2F2jRfFaccopMF0ZU_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05WqyS5wx_2F76bPvRNtCfQRpwLeF6ndXgSl7uWqtg9K4NGxwAvnrcw2fRo8N1wTjK58tBRgn9PFqJlD_2BP6NBB2HDzHWmZipSJTsIUq_2F7_2BnU86858wQHli245Dv5BTvBArIEkEifJPLMs5Fj6BYqv2kAk_2F81ygcrLPSLIGjSNtEbtbe1n_2BfAmCvEV_2BvRZfy_2Fuu9MKdz___Donations__Donation_Received__You_have_just_received_a_contribution_of___250_00___The_donor_s_contact__details_are_below__You_may_check_on_all_contributions_to_your_site_in__the_Donations__panel___http___sg_links_squarespace_com_ls_click_upn_kSeIUCMfD4NT8AUhFgOU0f8rNtUU_2BufoS1IMD73WVfIBZXlzxIwQH3fCumh6Dfr3ZvhBOJAPwsajb86l0bLSgOTcHUPef_2FgVEvbgcEQE6JA_3DxCgR_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05Wqy8Wx5EVfK2QOg3vW7lr9s5EYWnGiZcLK_2FHFMLhbBBmSpTwBBd3WriV8fu_2Fsm9grV1jOed0IsCJQ6QjPFeh6DCUwjv_2BYttvLWFh3OryyxBPu4a_2FI_2BdB4GvfKtMNgqdESjAXcwNwWSZNgEdqc3Rs6JJUHQ14W_2F63y1G7jz7Q015ybfORrxcUHror6j_2BU7TdGR1A______You_can_check_your_updated_balance_at_Stripe___http___sg_links_squarespace_com_ls_click_upn_anL_2FE0qPuv5EOFctfHcdiCQUCaxVtmwwBG0l3ttJrGg_3D7e_N_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05WqyRzrTDSd9lAjQHvc_2BfJo6fYW8W6bZNkaAYZfFnqqAA8upCyULd_2BeLWLyd9INfXNre35dzLmhXeLlWOtCLH6kJCtQqNfpUZ_2BoIkl6ErhW61Hc11TAjlYAs2c4_2FXGGd2YsR5scg8AJc27UMH3IwrbGoJdCeqLCVwVL3hDWi53MqX7ZRlMOrtCS6hK6W1SnQX_2BQ5______Donor_Name___Robert_Greenberg__Donor_Email___rgreenberg_614co_com__Donor_Address_____18635_North_101st_Place____SCOTTSDALE__AZ__85255____United_States__Donor_Phone_Number___6128673320__Additional_Information___Employer___The_614_Company__View_My_Donations___http___sg_links_squarespace_com_ls_click_upn_kSeIUCMfD4NT8AUhFgOU0f8rNtUU_2BufoS1IMD73WVfIBZXlzxIwQH3fCumh6Dfr3ZvhBOJAPwsajb86l0bLSgOTcHUPef_2FgVEvbgcEQE6JA_3DIjNM_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05Wqyjzk3RiR_2BzAdfOB_2Fcx6SQVtZtGQZvRqaR6t9ekxXOm6YMxYv0mvEyFAzKOgLGLE1QWOZkIdVWSf0AxwHpFYeeg_2BZHaOEh8GwQATigDjAyVlW1yN17JHANB7RrVA5yZ6o2Zu4MvtjKtaMsUFVvnk6jTTouH4E82w9YTg7m2fIJvhS4mEGl4bgkS56_2Bmkw4vzOU___If_you_have_any_questions__our_award_winning_Customer_Care_Team_is__available_24_7_at_support_squarespace_com___http___sg_links_squarespace_com_ls_click_upn_kSeIUCMfD4NT8AUhFgOU0W329IaGovFBkUE0tj7obNGq6Va5rmS1jiZlOUiMLgeE4rMR_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05WqyPTXc2_2FvvMvr1Tp3_2FQ9DDlvPNcDHKOqBfjaClyeUdCDuTeOM8UNirrU00cIFwwSrp5Hc1tWNjiv_2FhnXPhlGd8KGT9U8PLnDNc0lSQ99JORZxXMTxF2DzmT6QhIIbtNhzS_2FHVCNuWrIG3dw2xRCi_2BPjBYVhCraKESzXI4wxdL2GfUikNnnms227XO1V43yULRd______blog___http___sg_links_squarespace_com_ls_click_upn_iU_2Fy61EDDa_2BAyqB4MBMYYfmErk0g2qoS7_2BccR83QzJLTpZP4c2s1vZniF8SPdkEO6UtO_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05Wqyo7_2BM7BsGz_2BCOcO2k0zYAFE1n4HdaveKPB5cNQJlExzopeMiHXd_2BUyObAghciHZ9kZW9gOlBSetz19KPntQefX0rkYVpMkjTYjpwSwSW32yRaKMj9ZfEwfUEGRRcwzrGWQI9Acf9MOKTeq7QPPTPjPnRWQdmuL6gIYsvHigCCG85brxlfnQYBNPhiK3V9N1C4_____Help___Support___http___sg_links_squarespace_com_ls_click_upn_Kcv12ZDRqV_2FSlMg3SUgdI0uNdaFyIBNFJ26Sqak3v2q9Bw4Fkyx_2BY7nwIKNAoqnMVPuV_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05WqyABxAnEo6v1VyfnetnHKf6cMvyd1yPcBZOnbVperaV7oZVay6ICb_2BL5RhJOJTmbsog_2BzB6NXqF7c5M1pbWtZrG0SFeJfXuetZdAEJ5k4w290m2_2FmnzD8O_2FY1geaOqPhdkfb_2BCJQac517RsMQ53W6pxCCcjrcPpgo7loo2lFSsHQ52pUwsvPEoxP_2FQhFCcw7Ym_____Forum___http___sg_links_squarespace_com_ls_click_upn_kSeIUCMfD4NT8AUhFgOU0bBe5o7Zy64fV24gfBm0NqgP4EDCf1yvlRmIJuWb9xyREsLY_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05WqylUwE1E7tZANfa2UPvjg1ixZ5ycC6jVBs5c10c6eCYQkAdLrAnWKe4t8zJk7xCZshEuDUum0ymd3pGkvSOtmNnE0G9mUsmAefvFsrUjJfI62Ai4jp2ykl6kSIA8zTfjap_2BV3Z1Z4zV5isO8T0eBaUaO3t3VtqsR_2BS_2B4rSr6PeOjudd0uQ8RpIEcUDeAsESiyu_____Contact_Us___http___sg_links_squarespace_com_ls_click_upn_kSeIUCMfD4NT8AUhFgOU0W329IaGovFBkUE0tj7obNFTMYF2epVZM_2FoV1L_2FNz5fnffkl3uVViJ04XjOjSGv8Eg_3D_3D9_IJ_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05Wqyec5EyYkQPjkwron6AC_2FyvaAccttQDfD4tZwfV2REisoZjEcv45UlAuKFwjmOtpa2cN0wS8uNUC14ttasGG5IqawBkXe_2BXOR2xUbQKQSdmEn50jEVQ7KmXJbdm_2F2MchjWuBka3IaSmlFg1JD76q2K_2FwS_2FSR0NVdRqc7nyYoaAJRRdi9OSAp59crchlM3Lux5Z_____Twitter___http___sg_links_squarespace_com_ls_click_upn_kSeIUCMfD4NT8AUhFgOU0aPbOO2vN43VclhytZ60mFX4LtuFQ8FCQq3Uf2H7PUTdffao_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05WqyLAmwHZXUrIHTALj5IDhDH1hGnI3mffuH3h_2FVUY65kUNsaAvPeR7IjhBuyZtqpJ7O9NWA_2BuxjhjrFknvB0frGFneAGdLbc7f5NFAiSpN7bHKZahg8ahPPzBCUaGZ8CKMP3Ywkl95W3cKBSBD5oSoOsibM0DKrQ87TroIO1pHGZKy9exok0DOZtYQf2JzQtMf2_____Instagram___http___sg_links_squarespace_com_ls_click_upn_kSeIUCMfD4NT8AUhFgOU0dPSN2r2C_2BxGC_2Bh7Cng1I1cNySJ9ZVFt9KrImJX5C4stJxxK_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05WqyocRWCiEh3q1EP8j81CvPWGMMGrTuiLmETW32z2Tne196w6TK07CtmPCh23xsoT_2BfC6YDSr68KAbpyTuyMOqEzD8MvlE2HcyUv_2FrvS5EGTdLnbBrLh4o_2FbSv3ZFu7eJTfB81m0gex_2BqBC7aQ1wzFrso_2BppxjuQCgp3E7EwQaYVGBS36k1Xc7c1NxaaJyRzUHQ___Squarespace__225_Varick_Street__12th_Floor__New_York__NY_10014___image__squarespace____http___sg_links_squarespace_com_ls_click_upn_anL_2FE0qPuv5EOFctfHcdiDx9zoX7rQG4mQFjQobgOjl6v3dH_2BqsY_2F2jRfFaccopMftjE_P_2BU_2B_2FdZ8K3VSiSvfxFFQsfnkL0zV0QLzPLKgsFAjTTatcKKDYyvvNPFnEf5Xb3fqt6zyxb233dMr6lS_2BEkrEHOdJAUdQYG7Vk7EOEjEgGOTgQ1pcizwHIzFuzN2O3XaugoDjyLWVRsiHCnlM0VCK28jqONNA6PH1OLhmCDYCYlWZFVxFHljaZ_2BfbakKVlmUnBAcpzGMA7R6EtMd_2Bst_2FImENw1gSLHTXltYvUZpsPQtwlpHKE1S0C9t_2FT_2F01l1Gxp5fl2NR3rCTBTcZDJanMSnl8H8w2084rwLNlQGPKhgegEi2R328_2FIB3bS3lY7riv3hzo3LIk9Tz8d6_2Fyzh96fbp5e_2Fd0_2BvEq35xZ_2B0Of7ysyX5Yrd7YSckwO7C9_2BWFqOm2OL5PoQCTc3ku17EiXUteGc6rLzyzY4el_2B2VvAj1rKZMvLRk9sBXVZ9mQbM05Wqy12HNZszvdUc4FHm2Fmm0T9vHzaE9uEqIJhk22Xp8y7EAL9YFntF9H3DYlYIGXacyRWSpNP2y5XcS6Z1NN1iqrEZsifIej0NAdiVWSj0aenqyt4cfVaMzGmCjpKy3_2BA295CH_2ByAPBOPKTHeNmvgDQwh1IoQq08FHOmU3NviV6PDUVqVvqRnBWczqQWHW11PW_2B___'





# donor_name = search_donor_name('Donor_Name', a)
# print(donor_name)
# donor_email = search_donor_email('Donor_Name', a)
# print(donor_email)
# donor_adress = search_donor_adress('Donor_Name', a)
# print(donor_adress, 'FINAL')
# donor_number = search_donor_number('Donor_Name', a)
# print(donor_number)
# donor_additional = search_donor_additional('Donor_Name', a)
# print(donor_additional, 'FINAL')