from datetime import datetime
from dotenv import load_dotenv
import re
import time
import os
import schedule
import logging
import paramiko
import requests

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/app/logs/app.log")
    ]
)
logger = logging.getLogger(__name__)

SSH_HOST = os.getenv("HOST_IP", "linfed.ru")
SSH_USER = os.getenv("SSH_USER")
SSH_PRIVATE_KEY = os.getenv("SSH_KEY")
if SSH_PRIVATE_KEY is not None:
    key = SSH_PRIVATE_KEY.encode().decode("unicode_escape")
    with open("ssh_key", "w") as file:
        file.write(key)
        logger.info(f"Ssh_key loaded! - {datetime.now().isoformat()}")
else:
    logger.error(f"Error get ssh_key file - {datetime.now().isoformat()}")

def check_version():
    logger.info(f"Starting checking version - {datetime.now().isoformat()}")
    try:
        ssh = None

        logger.info(f"Getting server version - {datetime.now().isoformat()}")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SSH_HOST, username=SSH_USER, key_filename="ssh_key")
        stdin, stdout, stderr = ssh.exec_command('grep -w "PatchVersion" msm.d/cs2/base/game/csgo/steam.inf')
        output = stdout.read().decode()
        error = stderr.read().decode()

        if error.strip():
            logger.warning(f"Cannot read steam.inf file: {error} - {datetime.now().isoformat()}")
            return

        server_version = str(re.sub(r"\D", "", output))
        logger.info(f"Server version: {server_version}")

        logger.info(f"Getting app version - {datetime.now().isoformat()}")

        key = os.getenv("STEAM_WEB_API_KEY")
        params = {"key": key}
        response = requests.get("https://api.steampowered.com/ICSGOServers_730/GetGameServersStatus/v1/", params=params)

        if  not response.ok:
            logger.warning(f"Couldn't get version from API: {response.status_code} - {datetime.now().isoformat()}")
            return

        data = response.json()
        app_version = str(data["result"]["app"]["version"])
        logger.info(f"App version: {app_version}")

        if server_version != app_version:
            logger.info(f"Server version is outdated - {datetime.now().isoformat()}")

            logger.info(f"Getting status servers - {datetime.now().isoformat()}")
            status_response = requests.get("https://dev.linfed.ru/api/servers")

            if not status_response.ok:
                logger.warning(f"Couldn't get server status: {status_response.status_code}")
                return

            status_data = status_response.json()

            for status in status_data:
                if status["status"] == "online":
                    logger.info(f"Sending alert - {datetime.now().isoformat()}")
                    for _ in range(3):
                        ssh.exec_command(f'cs2-server @prac{status["id"]} exec say CS2  HAS BEEN UPDATED, NEED TO UPDATE SERVER')

                    ssh.exec_command(f'cs2-server @prac{status["id"]} exec say AFTER THE UPDATE, YOU NEED TO START THE SERVER IMMEDIATELY')
                    time.sleep(60)

            for status in status_data:
                    if status["status"] == "online":
                        logger.info(f"Stop servers {datetime.now().isoformat()}")
                        ssh.exec_command(f'cs2-server @prac{status["id"]} stop')

            logger.info(f"Starting server update - {datetime.now().isoformat()}")
            cout = ssh.exec_command('cs2-server update')
            com_out = cout.read().decode()
            logger.warning(f"Output - {com_out}")
        else:
            logger.info(f"Server is up to date! Current version{server_version} - {datetime.now().isoformat()}")

    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
    finally:
        ssh.close()

def run_scheduler():
    schedule.every(10).minutes.do(check_version)

    check_version()

    logger.info("Scheduler starting")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()
