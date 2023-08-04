from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from webbrowser import open_new_tab
from requests import get, post
from requests.structures import CaseInsensitiveDict
from datetime import datetime
from plyer import notification
from json import load
from time import time, sleep
from pathlib import Path
from distutils.util import strtobool
from argparse import ArgumentParser
from rich.console import Console
from rich.text import Text
from pypasser import reCaptchaV3
import os.path

import sys
import paramiko
import traceback
import urllib3

config = load(open(f'{Path(__file__).parent}/config/config.json'))



class ProlificUpdater:
    def __init__(self, bearer = None):
        self.participantId = config["Prolific_ID"]
        self.socksProxy = config['socks_proxy']
        if bearer: self.bearer = bearer
        else: self.bearer = "Bearer " + self.get_bearer_token()
        self.oldResults = list()

    def getRequestFromProlific(self):
        url = "https://internal-api.prolific.co/api/v1/participant/studies/"
        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Authorization"] = self.bearer

        return get(url,
           headers=headers,
           proxies={
               'http': config['socks_proxy'],
               'https': config['socks_proxy']
               }
           )
    
    def reservePlace(self, id):
        url = "https://internal-api.prolific.co/api/v1/submissions/reserve/"
        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"
        headers["Authorization"] = self.bearer
        postObj = {"study_id": id, "participant_id": self.participantId}

        return post(url,
            headers=headers,
            data=postObj,
            proxies={
               'http': config['socks_proxy'],
               'https': config['socks_proxy']
               }
            )

    def getResultsFromProlific(self):
        try:
            response = self.getRequestFromProlific()
        except Exception:
            print("Network error")
            notification.notify(
                title="Prolific update error {}".format(datetime.now().strftime("%H:%M:%S")),
                app_name="Prolific updater",
                message="Network error!",
                app_icon=f"{Path(__file__).parent}/assets/Paomedia-Small-N-Flat-Bell.ico",
                timeout=50
            )
            raise
        if response.status_code == 200:
            return response.json()['results']
        else:
            if not strtobool(config["auto_renew_bearer"]):
                print("Response error {}".format(response.status_code))
                print("Response error {}".format(response.reason))
                notification.notify(
                    title="Prolific update error {}".format(datetime.now().strftime("%H:%M:%S")),
                    app_name="Prolific updater",
                    message="Bearer error!",
                    app_icon=f"{Path(__file__).parent}/assets/Paomedia-Small-N-Flat-Bell.ico",
                    timeout=50
                )
                return list("bearer")
            else:
                print("Please renew bearer manually!")
                raise
                #self.bearer = self.get_bearer_token()
                #self.getResultsFromProlific()
            
    
    def get_bearer_token(self) -> str:
        print("Getting a new bearer token...")
        pageurl = 'https://internal-api.prolific.co/auth/accounts/login/'

        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-site-isolation-trials')
        options.add_argument('--headless')
        options.add_argument('--proxy-server=' + self.socksProxy)
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options= options)
        driver.get(pageurl)
        print("Driver launched")
        status = 0
        start = time()
        print("Trying to bypass captcha...")
        while not status:
            #anchor_url = "https://www.recaptcha.net/recaptcha/api2/anchor?ar=1&k=6LeMGXkUAAAAAOlMpEUm2UOldiq38QgBPJz5-Q-7&co=aHR0cHM6Ly9pbnRlcm5hbC1hcGkucHJvbGlmaWMuY286NDQz&hl=fr&v=gWN_U6xTIPevg0vuq7g1hct0&size=invisible&cb=igv4yino6y0f"
            anchor_url = "https://www.recaptcha.net/recaptcha/api2/anchor?ar=1&k=6LeMGXkUAAAAAOlMpEUm2UOldiq38QgBPJz5-Q-7&co=aHR0cHM6Ly9pbnRlcm5hbC1hcGkucHJvbGlmaWMuY286NDQz&hl=zh-CN&v=6MY32oPwFCn9SUKWt8czDsDw&size=invisible&cb=2z64pl74am1c"
            reCaptcha_response = reCaptchaV3(anchor_url)
            end = time()
            print(f"Captcha solved in {end-start}s")
            driver.execute_script(f'document.getElementsByName("username")[0].value = "{config["mail"]}"')
            driver.execute_script(f'document.getElementsByName("password")[0].value = "{config["password"]}"')
            print(reCaptcha_response)
            driver.execute_script(f'document.getElementById("g-recaptcha-response-100000").innerHTML="{reCaptcha_response}";')
            driver.find_element(By.ID, "login").submit()
            sleep(3)
            if driver.current_url =="https://internal-api.prolific.co/auth/accounts/login/":
                status = 0
                print("Failed to log in, retrying...")
                driver.get(pageurl)
                sleep(3)
                start = time()
                continue
            status = 1
            print(f"Refresh {driver.current_url}")
            driver.refresh()
            while True:
                for request in driver.requests:
                    if request.response:
                        if request.url.startswith("https://internal-api.prolific.co/openid/authorize?client_id="):
                            new_bearer = request.response.headers['location'].split("&")[0].split("access_token=")[-1]
                            print(f"Got a new bearer token ! : {new_bearer}")
                            return new_bearer
                    sleep(0.5)


    def executeCycle(self):
        try: results = self.getResultsFromProlific()
        except Exception: raise
        if results:
            if results != self.oldResults:
                self.reservePlace(id = results[0]["id"])
                notification.notify(
                    title="Prolific update {}".format(datetime.now().strftime("%H:%M:%S")),
                    app_name="Prolific updater",
                    message="New studies available!",
                    app_icon=f"{Path(__file__).parent}/assets/Paomedia-Small-N-Flat-Bell.ico",
                    timeout=50
                )
                a_website = "https://app.prolific.co/studies"  # TODO: open url in results
                open_new_tab(a_website)
        
        self.oldResults = results
        
        if results:
            return True
        else:
            if results == ["bearer"]:
                exit("Bearer token not valid anymore, need to change it !")
            return False    

def parseArgs():
    parser = ArgumentParser(description='Keep updated with Prolific')
    parser.add_argument('-b', '--bearer', type=str, help='bearer token')
    args = parser.parse_args()
    try:
        return {"bearer": "Bearer " + args.bearer}
    except TypeError:
        pass

def sshConnect(client):
    retry_count = 0
    while(retry_count < 5):
        try:
            client.connect(
                    hostname="127.0.0.1",
                    port=8022,
                    key_filename=os.path.join(os.path.expanduser('~'),'.ssh','id_ed25519'),
                    banner_timeout=50000
                    )
            client.open_socks_proxy(bind_address="127.0.0.1", port=8899)
            return
        except paramiko.ssh_exception.NoValidConnectionsError:
            # Needs to run adb forward! Will print this Exception even though usb is connected!
            print("SSH port on Phone is not reachable! Check whether adb forward is running or Phone is connected by USB")
        except paramiko.ssh_exception.SSHException:
            print("SSH Daemon not found! Has sshd started on Phone?")
        except Exception:  # catch all exception
            print("Exception caught")
        
        retry_count += 1
        print("Starting SOCKS proxy failed! Retry in 5s...")
        sleep(5)
    
    print("Retries exceeded. Exit now...")
    client.close()
    sys.exit()

if __name__ == "__main__":
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    myArguments = parseArgs()
    p_updater = None

    console = Console()
    status = console.status("[bold blue] Waiting for study...",spinner="arc")

    while (True):
        sshConnect(c)

        try:
            if strtobool(config["auto_renew_bearer"]) and not myArguments:
                p_updater = ProlificUpdater()
            else:
                p_updater = ProlificUpdater(bearer = myArguments["bearer"])

            status.start()

            while(True):
                updateTime = 10
                if(p_updater.executeCycle()):
                    status.stop()
                    text = Text("Study found! Finish the study and press key to continue:")
                    text.stylize("bold red")
                    console.input(text)
                    updateTime = 15
                else:
                    updateTime = 10
                # sleep for 10 sec
                sleep(updateTime)
        except KeyboardInterrupt:
            c.close()
            status.stop()
            sys.exit()
        except Exception as e:
            c.close()
            status.stop()
            traceback.print_exc()
            input("Error! Check your proxy connection and press Enter to continue:")
