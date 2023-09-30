import json
import logging
import os
import tkinter as tk
from tkinter import messagebox
import requests
from pytube import YouTube
import re

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
    base_filename = os.path.basename(video_file_path).replace('video', '')

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
    else:
        logging.error(f'Échec de la publication de la vidéo sur la page Facebook. Détails de l\'erreur: {response.text}')


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
            else:
                logging.error(f'Échec de la finalisation de la publication du Reel sur la page Facebook. Détails de l\'erreur: {finish_response.text}')
        else:
            logging.error(f'Échec de l’upload du fichier pour le réel Facebook. Détails de l\'erreur: {upload_response.text}')
    else:
        logging.error(f'Échec de l’initialisation de la publication du Reel sur la page Facebook. Détails de l\'erreur: {response.text}')

def post_to_tiktok(video_path, video_title, video_description):
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
            return
        
        # Étape 2: Upload du fichier
        with open(video_path, 'rb') as video_file:
            upload_response = requests.post(upload_url, data=video_file.read())
        if upload_response.status_code != 200:
            logging.error(f'Échec de l’upload de la vidéo sur TikTok. Détails de l\'erreur: {upload_response.text}')
            print('Échec de l’upload de la vidéo sur TikTok.')
            print('Détails de l\'erreur:', upload_response.text)
            return
        
        # Étape 3: Confirmation
        confirm_url = f'https://open.tiktokapis.com/v2/post/publish/video/confirm/{video_id}'
        confirm_response = requests.post(confirm_url, headers=headers)
        if confirm_response.status_code == 200:
            logging.info('Vidéo publiée avec succès sur TikTok!')
        else:
            logging.error(f'Échec de la confirmation de la publication sur TikTok. Détails de l\'erreur: {confirm_response.text}')
    except Exception as e:
        logging.error(f'Erreur inattendue lors de la publication sur TikTok: {e}')


def post_to_instagram(video_url, video_title, video_description):
    container_url = f'https://graph.facebook.com/v18.0/{INSTAGRAM_USER_ID}/media'
    container_payload = {
        'image_url': video_url,
        'caption': f"{video_title}\n{video_description}",
        'access_token': INSTAGRAM_ACCESS_TOKEN
    }
    container_response = requests.post(container_url, data=container_payload)
    if container_response.status_code == 200:
        container_id = container_response.json().get('id')

        publish_url = f'https://graph.facebook.com/v18.0/{INSTAGRAM_USER_ID}/media_publish'
        publish_payload = {
            'creation_id': container_id,
            'access_token': INSTAGRAM_ACCESS_TOKEN
        }
        publish_response = requests.post(publish_url, data=publish_payload)
        if publish_response.status_code == 200:
            logging.info('Vidéo publiée avec succès sur Instagram!')
        else:
            logging.error(f'Échec de la publication de la vidéo sur Instagram. Détails de l\'erreur: {publish_response.text}')
    else:
        logging.error(f'Échec de la création du conteneur Instagram. Détails de l\'erreur: {container_response.text}')


class App:
    def __init__(self, root):
        self.root = root
        root.title("Publication Automatique de Vidéo")

        # ID de la vidéo YouTube
        self.label_video_id = tk.Label(root, text="ID de la vidéo YouTube:")
        self.label_video_id.pack()
        self.entry_video_id = tk.Entry(root)
        self.entry_video_id.pack()

        # Bouton de soumission
        self.submit_button = tk.Button(root, text="Publier la Vidéo", command=self.publish_video)
        self.submit_button.pack()

    def publish_video(self):
        video_id = self.entry_video_id.get()
        if not video_id:
            messagebox.showerror("Erreur", "L'ID de la vidéo YouTube est requis.")
            logging.error("L'ID de la vidéo YouTube est requis.")
            return

        try:
            youtube_url = f'https://www.youtube.com/watch?v={video_id}'
            path_to_save_video = PATH_TEMP_MEDIA
            downloaded_file_path = download_youtube_video(youtube_url, path_to_save_video)

            url = f'https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=snippet,contentDetails&key={YOUTUBE_API_KEY}'
            response = requests.get(url)
            video_details = response.json()

            video_title = video_details['items'][0]['snippet']['title']
            video_description = video_details['items'][0]['snippet']['description']

            #post_to_facebook(video_title, video_description, downloaded_file_path)
            #post_to_facebook_as_reel(video_title, video_description, downloaded_file_path)
            #post_to_tiktok(downloaded_file_path, video_title, video_description)
            #post_to_instagram(downloaded_file_path, video_title, video_description)

            # Supprimer la vidéo téléchargée
            #delete_file(downloaded_file_path)

            messagebox.showinfo("Succès", "La vidéo a été publiée avec succès!")
        except Exception as e:
            logging.error(f"Erreur lors de la publication de la vidéo: {e}")
            messagebox.showerror("Erreur", f"Erreur lors de la publication de la vidéo: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("300x300")
    app = App(root)
    root.mainloop()
