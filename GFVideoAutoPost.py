import json
import logging
import os
import tkinter as tk
from tkinter import messagebox
import requests
from pytube import YouTube
import re
import time

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
    if response.status_code == 200:
        status_response_json = json.loads(response.text)
        if status_response_json['status_code'] == 'FINISHED':
            print("ig media container is ready")
            return True
        else:
            print('waiting for ig media container to be ready...')
            time.sleep(30)  # Attendre 5 secondes avant de vérifier à nouveau
            return check_if_media_container_ready(status_url)  # Appel récursif
    else:
        print(f"Error Occurred while checking status: {response.text}")
        return False

def download_youtube_video(youtube_url, path_to_save_video):
    yt = YouTube(youtube_url)
    
    video_stream = None
    audio_stream = None
    
    # Obtenez le flux vidéo de la plus haute résolution
    video_stream = yt.streams.filter(adaptive=True, file_extension='mp4', only_video=True).first()
    # Obtenez le flux audio de la plus haute résolution
    audio_stream = yt.streams.filter(adaptive=True, file_extension='mp4', only_audio=True).first()
    
    # Si le flux vidéo ou audio n'est pas disponible, utilisez la résolution la plus élevée disponible
    if video_stream is None or audio_stream is None:
        ys = yt.streams.get_highest_resolution()
        file_path = ys.download(path_to_save_video)
        return file_path
    
    # Téléchargez les flux vidéo et audio séparément
    video_file_path = video_stream.download(output_path=path_to_save_video, filename_prefix='video')
    audio_file_path = audio_stream.download(output_path=path_to_save_video, filename_prefix='audio')

    # Obtenez le nom de base du fichier vidéo (sans extension)
    base_filename = os.path.basename(video_file_path).replace('.mp4', '')

    # Combinez les flux vidéo et audio
    output_file_path = os.path.join(path_to_save_video, f"{base_filename}_max_quality.mp4")
    os.system(f'ffmpeg -i "{video_file_path}" -i "{audio_file_path}" -c:v copy -c:a aac "{output_file_path}"')

    
    # Supprimez les fichiers vidéo et audio temporaires
    os.remove(video_file_path)
    os.remove(audio_file_path)
    
    return output_file_path


def post_to_facebook(video_title, video_description, video_url):
    print(FACEBOOK_PAGE_ID)
    print(FACEBOOK_ACCESS_TOKEN)

    facebook_url = f'https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/videos'
    with open(video_url, 'rb') as video_file:
        payload = {
            'title': video_title,
            'description': video_description,
            'access_token': FACEBOOK_ACCESS_TOKEN
        }
        files = {'source': (f'{video_title}.mp4', video_file, 'video/mp4')}
        response = requests.post(facebook_url, data=payload, files=files)

    if response.status_code == 200:
        logging.info('Vidéo publiée avec succès sur la page Facebook!')
        return 'Vidéo publiée avec succès sur Facebook!'
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
                'description': f"{video_title}\n{extract_hashtags(video_description)}"
            }
            finish_url = f'https://graph.facebook.com/{FACEBOOK_PAGE_ID}/video_reels'
            finish_response = requests.post(finish_url, data=finish_payload)
            
            if finish_response.status_code == 200:
                logging.info('Reel publié avec succès sur la page Facebook!')
                return 'Vidéo publiée avec succès sur Facebook Réel!'
            else:
                logging.error(f'Échec de la finalisation de la publication du Reel sur la page Facebook. Détails de l\'erreur: {finish_response.text}')
                return 'Echec Réel Facebook!'
        else:
            logging.error(f'Échec de l’upload du fichier pour le réel Facebook. Détails de l\'erreur: {upload_response.text}')
            return 'Echec Réel Facebook!'
    else:
        logging.error(f'Échec de l’initialisation de la publication du Reel sur la page Facebook. Détails de l\'erreur: {response.text}')
        return 'Echec Réel Facebook!'

def post_to_tiktok(video_title, video_description, video_path):
    try:
        # Étape 1: Initialisation
        init_url = 'https://open.tiktokapis.com/v2/post/publish/video/init/'
        headers = {
            'Authorization': f'Bearer {TIKTOK_ACCESS_TOKEN}',
            'Content-Type': 'application/json; charset=UTF-8'
        }
        post_info = {
            'title': video_title,
            'description': extract_hashtags(video_description),  # Ajout de la description ici
            'privacy_level': 'PUBLIC_TO_EVERYONE'
        }
        source_info = {
            'source': 'FILE_UPLOAD'
        }
        body = {
            'post_info': post_info,
            'source_info': source_info
        }
        response = requests.post(init_url, headers=headers, data=json.dumps(body))
        if response.status_code == 200:
            video_id = response.json().get('video_id')
            upload_url = response.json().get('upload_url')
        else:
            logging.error(f'Échec de l’initialisation de la publication sur TikTok. Détails de l\'erreur: {response.text}')
            return 'Echec TikTok!'
        
        # Étape 2: Upload du fichier
        with open(video_path, 'rb') as video_file:
            upload_response = requests.post(upload_url, data=video_file.read())
        if upload_response.status_code != 200:
            logging.error(f'Échec de l’upload de la vidéo sur TikTok. Détails de l\'erreur: {upload_response.text}')
            return 'Echec TikTok!'
        
        # Étape 3: Confirmation
        confirm_url = f'https://open.tiktokapis.com/v2/post/publish/video/confirm/{video_id}'
        confirm_response = requests.post(confirm_url, headers=headers)
        if confirm_response.status_code == 200:
            logging.info('Vidéo publiée avec succès sur TikTok!')
            return 'Vidéo publiée avec succès sur TikTok!'
        else:
            logging.error(f'Échec de la confirmation de la publication sur TikTok. Détails de l\'erreur: {confirm_response.text}')
            return 'Echec TikTok'
    except Exception as e:
        logging.error(f'Erreur inattendue lors de la publication sur TikTok: {e}')
        return 'Echec TikTok!'

def post_to_instagram(video_title, video_description, video_url):
    
    container_url = f'https://graph.facebook.com/v18.0/{INSTAGRAM_USER_ID}/media'
    print(video_url)
    container_payload = {
        'video_url': video_url,
        'media_type': 'REELS',
        'caption': f"{video_title}\n{video_description}",
        'access_token': INSTAGRAM_ACCESS_TOKEN
    }
    container_response = requests.post(container_url, data=container_payload)
    if container_response.status_code == 200:
        container_id = container_response.json().get('id')

        # Vérifier le Statut du Conteneur
        status_url = f'https://graph.facebook.com/v18.0/{container_id}?fields=status_code&access_token={INSTAGRAM_ACCESS_TOKEN}'
        container_ready = check_if_media_container_ready(status_url)
        
        if not container_ready:
            print("Media processing failed.")
            logging.error("Media processing failed.")
            return



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
        self.delete_file_var = tk.BooleanVar(value=True)
        self.delete_file_checkbutton = tk.Checkbutton(root, text="Supprimer le fichier de sortie", variable=self.delete_file_var)
        self.delete_file_checkbutton.pack()

        # Bouton de soumission
        self.submit_button = tk.Button(root, text="Publier la Vidéo", command=self.publish_video)
        self.submit_button.pack()

        self.facebook_checkbutton.pack(anchor='w')
        self.facebook_reel_checkbutton.pack(anchor='w')
        self.instagram_checkbutton.pack(anchor='w')
        self.tiktok_checkbutton.pack(anchor='w')
        self.delete_file_checkbutton.pack(anchor='w')

    def publish_video(self):
        video_id = self.entry_video_id.get()
        if not video_id:
            messagebox.showerror("Erreur", "L'ID de la vidéo YouTube est requis.")
            logging.error("L'ID de la vidéo YouTube est requis.")
            return

    
        youtube_url = f'https://www.youtube.com/watch?v={video_id}'
        path_to_save_video = PATH_TEMP_MEDIA
        downloaded_file_path = download_youtube_video(youtube_url, path_to_save_video)

        url = f'https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=snippet,contentDetails&key={YOUTUBE_API_KEY}'
        response = requests.get(url)
        video_details = response.json()

        video_title = video_details['items'][0]['snippet']['title']
        video_description = video_details['items'][0]['snippet']['description']

        messages = []

        # Vérifiez les variables BooleanVar pour savoir quelles actions effectuer
        if self.facebook_var.get():
            msg = post_to_facebook(video_title, video_description, downloaded_file_path)
            messages.append(msg)
        
        if self.facebook_reel_var.get():
            msg = post_to_facebook_as_reel(video_title, video_description, downloaded_file_path)
            messages.append(msg)
        
        if self.instagram_var.get():
            msg = post_to_instagram(video_title, video_description, downloaded_file_path)
            messages.append(msg)
        print(self.tiktok_var.get())
        if self.tiktok_var.get():
            msg = post_to_tiktok(video_title, video_description, downloaded_file_path)
            print(msg)
            messages.append(msg)
        
        if self.delete_file_var.get():
            delete_file(downloaded_file_path)

        messagebox.showinfo("Résultats de la publication", "\n".join(messages))

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("360x360")
    app = App(root)
    root.mainloop()
