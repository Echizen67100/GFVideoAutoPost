import json
import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import requests
from pytube import YouTube
import re
import time
import paramiko
import subprocess
import webbrowser
import unidecode

# Obtenez le chemin absolu du script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Changez le répertoire de travail au répertoire du script
os.chdir(script_dir)

# Configurer le logging
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Charger la configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Définir les variables globales
FACEBOOK_ACCESS_TOKEN = config.get('FACEBOOK_ACCESS_TOKEN')
TIKTOK_ACCESS_TOKEN = config.get('TIKTOK_ACCESS_TOKEN')
INSTAGRAM_ACCESS_TOKEN = config.get('INSTAGRAM_ACCESS_TOKEN')
INSTAGRAM_USER_ID = config.get('INSTAGRAM_USER_ID')
YOUTUBE_API_KEY = config.get('YOUTUBE_API_KEY')
FACEBOOK_PAGE_ID = config.get('FACEBOOK_PAGE_ID')
PATH_TEMP_MEDIA = config.get('PATH_TEMP_MEDIA')
FTP_USER = config.get('FTP_USER')
FTP_PSW = config.get('FTP_PSW')
FTP_HOST = config.get('FTP_HOST')
FTP_PORT = config.get('FTP_PORT')
URL_DISTANT_DOWNLOAD = config.get('URL_DISTANT_DOWNLOAD')

def wait_for_upload(local_file_path, remote_file_path, sftp):
    local_file_size = os.path.getsize(local_file_path)
    remote_file_size = sftp.stat(remote_file_path).st_size
    
    while local_file_size != remote_file_size:
        print("Waiting for the file to be uploaded...")
        time.sleep(5)  # attendre un certain temps avant de vérifier à nouveau
        remote_file_size = sftp.stat(remote_file_path).st_size

def clean_filename(filename):
    # Supprimer les accents
    filename = unidecode.unidecode(filename)
    # Remplacer tous les caractères non alphanumériques, espaces, tirets, underscores et points par des underscores
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    return filename

def copy_file_to_sftp(local_video_path):
    # Extraire le nom du fichier de local_video_path
    file_name = clean_filename(os.path.basename(local_video_path))
    
    # Définir le chemin du fichier distant
    remote_directory = ''
    remote_file_path = os.path.join(remote_directory, file_name)
    
    # Établir une connexion SFTP et télécharger le fichier
    transport = paramiko.Transport((FTP_HOST, int(FTP_PORT)))
    transport.connect(username=FTP_USER, password=FTP_PSW)
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    # Commencer le téléchargement du fichier sur SFTP
    sftp.put(local_video_path, remote_file_path)
    
    # Attendre que le fichier soit complètement téléchargé sur SFTP
    wait_for_upload(local_video_path, remote_file_path, sftp)
    
    # Fermer la connexion SFTP
    sftp.close()
    transport.close()
    
    # Retourner l'URL du fichier distant
    return f'{URL_DISTANT_DOWNLOAD}{remote_file_path}'

def extract_hashtags(description):
    hashtags = re.findall(r"#\w+", description)
    return ' '.join(hashtags)

def delete_file(file_path):
    try:
        os.remove(file_path)
        print(f"Le fichier {file_path} a été supprimé avec succès.")
    except OSError as e:
        print(f"Erreur lors de la suppression du fichier {file_path}. Raison : {e.strerror}")

def check_if_media_container_ready(status_url):
    response = requests.get(status_url)
    print(response.text)
    if response.status_code == 200:
        status_response_json = json.loads(response.text)
        if status_response_json['status_code'] == 'FINISHED':
            print("ig media container is ready")
            return True
        else:
            print('waiting for ig media container to be ready...')
            time.sleep(30)
            return check_if_media_container_ready(status_url)
    else:
        print(f"Error Occurred while checking status: {response.text}")
        return False

def download_youtube_video(youtube_url, path_to_save_video):
    yt = YouTube(youtube_url)
    video_stream = None
    audio_stream = None
    video_stream = yt.streams.filter(adaptive=True, file_extension='mp4', only_video=True).first()
    audio_stream = yt.streams.filter(adaptive=True, file_extension='mp4', only_audio=True).first()
    
    if video_stream is None or audio_stream is None:
        ys = yt.streams.get_highest_resolution()
        file_path = ys.download(path_to_save_video)
        return file_path
    
    video_file_path = video_stream.download(output_path=path_to_save_video, filename_prefix='video')
    audio_file_path = audio_stream.download(output_path=path_to_save_video, filename_prefix='audio')
    base_filename = os.path.basename(video_file_path).replace('video', '')
    clean_base_filename = re.sub(r'[^\w\-_\. ]', '_', base_filename)
    output_file_path = os.path.join(path_to_save_video, f"{clean_base_filename}_max_quality.mp4")
    os.system(f'ffmpeg -i "{video_file_path}" -i "{audio_file_path}" -c:v copy -c:a aac "{output_file_path}"')
    compatible_file_path = os.path.join(path_to_save_video, f"{clean_base_filename}_compatible.mp4")
    subprocess.run([
        'ffmpeg', '-i', output_file_path, '-c:v', 'libx264', '-b:v', '3500k', 
        '-pix_fmt', 'yuv420p', '-crf', '23', '-c:a', 'aac', '-b:a', '189k',
        '-movflags', '+faststart', compatible_file_path
    ])
    
    os.remove(video_file_path)
    os.remove(audio_file_path)
    os.remove(output_file_path)
    return compatible_file_path

def post_to_facebook(video_title, video_description, path_to_video):
    print(FACEBOOK_PAGE_ID)
    print(FACEBOOK_ACCESS_TOKEN)

    facebook_url = f'https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/videos'
    with open(path_to_video, 'rb') as video_file:
        payload = {
            'title': video_title,
            'description': video_description,
            'access_token': FACEBOOK_ACCESS_TOKEN
        }
        files = {'source': (f'{video_title}.mp4', video_file, 'video/mp4')}
        response = requests.post(facebook_url, data=payload, files=files)

    if response.status_code == 200:
        logging.info('Vidéo publiée avec succès sur la page Facebook!')
        return 'Vidéo publiée avec succès sur la page Facebook!'
    else:
        logging.error(f'Échec de la publication de la vidéo sur la page Facebook. Détails de l\'erreur: {response.text}')
        return 'Echec Facebook!'


def post_to_facebook_as_reel(video_title, video_description, path_to_video):
    # Initialisation de l'upload
    facebook_url = f'https://graph.facebook.com/{FACEBOOK_PAGE_ID}/video_reels'
    payload = {
        'title': video_title,
        'description': video_description,
        "upload_phase": "start",
        'access_token': FACEBOOK_ACCESS_TOKEN
    }
    response = requests.post(facebook_url, data=payload)
    
    if response.status_code == 200:
        video_id = response.json().get('video_id')
        upload_url = response.json().get('upload_url')
        
        # Upload du fichier vidéo
        file_size = os.path.getsize(path_to_video)
        headers = {
            'Authorization': f'OAuth {FACEBOOK_ACCESS_TOKEN}',
            'offset': '0',
            'file_size': str(file_size)
        }
        with open(path_to_video, 'rb') as video_file:
            upload_response = requests.post(upload_url, headers=headers, data=video_file)
        
        if upload_response.status_code == 200:
            # Finalisation de l'upload
            finish_payload = {
                'access_token': FACEBOOK_ACCESS_TOKEN,
                'video_id': video_id,
                'upload_phase': 'finish',
                'video_state': 'PUBLISHED',
                'description': f"{video_title}\n{video_description}"
            }
            finish_url = f'https://graph.facebook.com/{FACEBOOK_PAGE_ID}/video_reels'
            finish_response = requests.post(finish_url, data=finish_payload)
            
            if finish_response.status_code == 200:
                logging.info('Reel publié avec succès sur la page Facebook!')
                return 'Reel publié avec succès sur la page Facebook!'
            else:
                logging.error(f'Échec de la finalisation de la publication du Reel sur la page Facebook. Détails de l\'erreur: {finish_response.text}')
                return 'Echec Facebook Reel!'
        else:
            logging.error(f'Échec upload du fichier pour le réel Facebook. Détails de l\'erreur: {upload_response.text}')
            return 'Echec Facebook Reel!'
    else:
        logging.error(f'Échec initialisation de la publication du Reel sur la page Facebook. Détails de l\'erreur: {response.text}')
        return 'Echec Facebook Reel!'



def post_to_instagram(video_title, video_description, path_to_video):
    # Utilisez l'URL de la vidéo sur le serveur pour la publication Instagram
    video_url = path_to_video
    print(video_url)
    container_url = f'https://graph.facebook.com/v18.0/{INSTAGRAM_USER_ID}/media'
    container_payload = {
        'video_url': video_url,
        'media_type': 'REELS',
        'caption': f"{video_title}\n{video_description}",
        'access_token': INSTAGRAM_ACCESS_TOKEN
    }
    container_response = requests.post(container_url, data=container_payload)
    if container_response.status_code == 200:
        container_id = container_response.json().get('id')
        status_url = f'https://graph.facebook.com/v18.0/{container_id}?fields=status_code,status&access_token={INSTAGRAM_ACCESS_TOKEN}'
        container_ready = check_if_media_container_ready(status_url)
        
        if not container_ready:
            logging.error("Media processing failed.")
            return 'Echec Instagram!'
        
        publish_url = f'https://graph.facebook.com/v18.0/{INSTAGRAM_USER_ID}/media_publish'
        publish_payload = {
            'creation_id': container_id,
            'access_token': INSTAGRAM_ACCESS_TOKEN
        }
        publish_response = requests.post(publish_url, data=publish_payload)
        if publish_response.status_code == 200:
            logging.info('Vidéo publiée avec succès sur Instagram!')
            return 'Vidéo publiée avec succès sur Instagram!'
        else:
            logging.error(f'Échec de la publication de la vidéo sur Instagram. Détails de l\'erreur: {publish_response.text}')
            return 'Echec Instagram!'
    else:
        logging.error(f'Échec de la création du conteneur Instagram. Détails de l\'erreur: {container_response.text}')
        return 'Echec Instagram!'

def post_to_tiktok(video_title, video_description, path_to_video):
    tiktok_url = 'https://open-api.tiktok.com/v2/video/upload/'
    headers = {
        'access_token': TIKTOK_ACCESS_TOKEN,
        'Content-Type': 'multipart/form-data'
    }
    with open(path_to_video, 'rb') as video_file:
        files = {'video': (f'{video_title}.mp4', video_file, 'video/mp4')}
        response = requests.post(tiktok_url, headers=headers, files=files)
    if response.status_code == 200:
        video_id = response.json().get('video_id')
        logging.info('Vidéo publiée avec succès sur TikTok!')
        return 'Vidéo publiée avec succès sur TikTok!', video_id
    else:
        logging.error(f'Échec de la publication de la vidéo sur TikTok. Détails de l\'erreur: {response.text}')
        return 'Echec TikTok!'

class App:
    def __init__(self, root):
        self.root = root
        root.title("Publication Automatique de Vidéo")

        # ID de la vidéo YouTube
        self.label_video_id = tk.Label(root, text="ID de la vidéo YouTube:")
        self.label_video_id.pack()
        self.entry_video_id = tk.Entry(root)
        self.entry_video_id.pack()

        # Cases à cocher pour chaque réseau social
        self.facebook_var = tk.BooleanVar(value=True)
        self.facebook_checkbutton = tk.Checkbutton(root, text="Facebook", variable=self.facebook_var)
        self.facebook_checkbutton.pack()

        self.facebook_reel_var = tk.BooleanVar(value=True)
        self.facebook_reel_checkbutton = tk.Checkbutton(root, text="Réel Facebook", variable=self.facebook_reel_var)
        self.facebook_reel_checkbutton.pack()

        self.instagram_var = tk.BooleanVar(value=True)
        self.instagram_checkbutton = tk.Checkbutton(root, text="Instagram", variable=self.instagram_var)
        self.instagram_checkbutton.pack()

        self.tiktok_var = tk.BooleanVar(value=True)
        self.tiktok_checkbutton = tk.Checkbutton(root, text="TikTok", variable=self.tiktok_var)
        self.tiktok_checkbutton.pack()

        # Option pour supprimer le fichier de sortie
        #self.delete_file_var = tk.BooleanVar(value=True)
        #self.delete_file_checkbutton = tk.Checkbutton(root, text="Supprimer le fichier de sortie", variable=self.delete_file_var)
        #self.delete_file_checkbutton.pack()

        self.select_file_button = tk.Button(root, text="Sélectionner un fichier vidéo", command=self.select_file)
        self.select_file_button.pack()

        self.file_path_var = tk.StringVar(value="Fichier Sélectionné: Aucun")
        self.file_path_label = tk.Label(root, textvariable=self.file_path_var)
        self.file_path_label.pack()

        # Bouton de soumission
        self.submit_button = tk.Button(root, text="Publier la Vidéo", command=self.publish_video)
        self.submit_button.pack()

        # Bouton pour télécharger la vidéo YouTube
        self.download_button = tk.Button(root, text="Télécharger la Vidéo YouTube", command=self.download_youtube_video)
        self.download_button.pack()

        self.open_folder_button = tk.Button(root, text="Ouvrir le dossier contenant le fichier", command=self.open_folder)
        self.open_folder_button.pack()
        self.open_folder_button.config(state=tk.DISABLED)  # Désactivez le bouton par défaut

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Fichiers vidéo", "*.mp4")])
        if file_path:
            self.file_path_var.set(f"Fichier Sélectionné: {file_path}")
            logging.info(f"Fichier vidéo sélectionné: {file_path}")
           

    def open_folder(self):
        file_path = self.file_path_var.get().split(": ")[1]
        if file_path and file_path != "Aucun":
            folder_path = os.path.dirname(file_path)
            webbrowser.open(folder_path)

    def publish_video(self):
        file_path = self.file_path_var.get().split(": ")[1]
        if not file_path or file_path == "Aucun":
            messagebox.showerror("Erreur", "Un fichier vidéo est requis.")
            logging.error("Un fichier vidéo est requis.")
            return

        # Récupérer le titre et la description de la vidéo YouTube si un ID YouTube est fourni
        video_id = self.entry_video_id.get()
        video_title = ""
        video_description = ""
        if video_id:
            url = f'https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=snippet,contentDetails&key={YOUTUBE_API_KEY}'
            response = requests.get(url)
            video_details = response.json()
            video_title = video_details['items'][0]['snippet']['title']
            video_description = video_details['items'][0]['snippet']['description']
        else:
            video_title = "Titre par défaut"  # Remplacez par le titre souhaité si aucun ID YouTube n'est fourni
            video_description = "Description par défaut"  # Remplacez par la description souhaitée si aucun ID YouTube n'est fourni

        messages = []

        # Copiez le fichier sur SFTP et obtenez l'URL du fichier
        if self.instagram_var.get():
            file_url = copy_file_to_sftp(file_path)
        
        messages = []
        
        if self.facebook_var.get():
            msg = post_to_facebook(video_title, video_description, file_path)  
            messages.append(str(msg))
        
        if self.facebook_reel_var.get():
            msg = post_to_facebook_as_reel(video_title, video_description, file_path)  
            messages.append(str(msg))

        if self.instagram_var.get():
            msg = post_to_instagram(video_title, video_description, file_url)
            messages.append(msg)

        if self.tiktok_var.get():
            msg = post_to_tiktok(video_title, video_description, file_path)
            messages.append(msg)

        #if self.delete_file_var.get():
        #    delete_file(file_path)

        messagebox.showinfo("Résultats de la publication", "\n".join(messages))

    def download_youtube_video(self):
        video_id = self.entry_video_id.get()
        if not video_id:
            messagebox.showerror("Erreur", "L'ID de la vidéo YouTube est requis.")
            logging.error("L'ID de la vidéo YouTube est requis.")
            return

        youtube_url = f'https://www.youtube.com/watch?v={video_id}'
        path_to_save_video = PATH_TEMP_MEDIA
        downloaded_file_path = download_youtube_video(youtube_url, path_to_save_video)
        self.file_path_var.set(f"Fichier Sélectionné: {downloaded_file_path}")
        logging.info(f"Fichier vidéo téléchargé: {downloaded_file_path}")
        self.open_folder_button.config(state=tk.NORMAL)  # Activez le bouton pour ouvrir le dossier après le téléchargement

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("600x600")  # Fenêtre agrandie
    app = App(root)
    root.mainloop()