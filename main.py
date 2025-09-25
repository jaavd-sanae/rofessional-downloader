import flet as ft
import requests
import re
import os
import threading
import tempfile
from urllib.parse import urlparse, unquote
import json
from pytube import *

# تشخیص محیط اندروید
ANDROID = "ANDROID_DATA" in os.environ

def main(page: ft.Page):
    # تنظیمات صفحه برای موبایل
    page.title = "دانلودر حرفه‌ای"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = "#667eea"
    
    # آیکون‌های base64 برای جلوگیری از مشکل لینک‌های خارجی
    INSTAGRAM_ICON = "https://cdn-icons-png.flaticon.com/512/2111/2111463.png"
    YOUTUBE_ICON = "https://cdn-icons-png.flaticon.com/512/1384/1384060.png"
    
    # توابع navigation
    def go_to_instagram(e):
        page.clean()
        page.add(instagram_page)
    
    def go_to_youtube(e):
        page.clean()
        page.add(youtube_page)
    
    def go_to_main(e):
        page.clean()
        page.add(main_container)
    
    # تابع دریافت مسیر دانلود بهینه‌شده
    def get_download_path():
        if ANDROID:
            try:
                # مسیرهای مختلف برای اندروید
                paths = [
                    "/storage/emulated/0/Download/ProfessionalDownloader",
                    "/sdcard/Download/ProfessionalDownloader",
                    "/storage/sdcard0/Download/ProfessionalDownloader"
                ]
                for path in paths:
                    try:
                        os.makedirs(path, exist_ok=True)
                        # تست نوشتن در مسیر
                        test_file = os.path.join(path, "test.txt")
                        with open(test_file, "w") as f:
                            f.write("test")
                        os.remove(test_file)
                        return path
                    except:
                        continue
                return "/storage/emulated/0/Download"
            except Exception as e:
                return tempfile.gettempdir()
        else:
            path = os.path.join(tempfile.gettempdir(), "Downloader")
            os.makedirs(path, exist_ok=True)
            return path
    
    # تابع اسکن فایل برای اندروید
    def scan_file(file_path):
        if ANDROID:
            try:
                from android.storage import app_storage_path
                from jnius import autoclass
                MediaScannerConnection = autoclass('android.media.MediaScannerConnection')
                Context = autoclass('android.content.Context')
                MediaScannerConnection.scanFile(
                    page.platform_bridge.context, 
                    [file_path], 
                    None, 
                    None
                )
                return True
            except:
                return True  # اگر اسکنر کار نکرد، حداقل فایل ذخیره شده
        return True
    
    # تابع دانلود فایل
    def download_file(url, filename, file_type="instagram"):
        try:
            download_path = get_download_path()
            file_path = os.path.join(download_path, filename)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # آپدیت progress bar
                        if total_size > 0:
                            progress = downloaded_size / total_size
                            if file_type == "instagram":
                                insta_progress_bar.value = progress
                            else:
                                youtube_progress_bar.value = progress
                            page.update()
            
            # اسکن فایل برای گالری
            scan_file(file_path)
            return True, file_path
            
        except Exception as e:
            return False, str(e)
    
    # تابع دانلود اینستاگرام با API ساده
    def download_instagram(url):
        try:
            # استخراج shortcode از لینک
            if "/p/" in url:
                shortcode = url.split("/p/")[1].split("/")[0].split("?")[0]
            elif "/reel/" in url:
                shortcode = url.split("/reel/")[1].split("/")[0].split("?")[0]
            else:
                return False, "لینک معتبر نیست"
            
            # استفاده از API عمومی برای دریافت اطلاعات پست
            api_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(api_url, headers=headers, timeout=30)
            if response.status_code != 200:
                return False, "خطا در دریافت اطلاعات پست"
            
            data = response.json()
            
            # استخراج URL مدیا
            media_url = None
            try:
                graphql = data.get('graphql', {})
                shortcode_media = graphql.get('shortcode_media', {})
                
                if shortcode_media.get('is_video'):
                    media_url = shortcode_media.get('video_url')
                else:
                    # برای عکس‌ها
                    edges = shortcode_media.get('edge_sidecar_to_children', {}).get('edges', [])
                    if edges:
                        media_url = edges[0]['node'].get('display_url')
                    else:
                        media_url = shortcode_media.get('display_url')
                
                if not media_url:
                    return False, "مدیا پیدا نشد"
                
                # دانلود فایل
                filename = f"instagram_{shortcode}_{os.path.basename(urlparse(media_url).path)}"
                success, result = download_file(media_url, filename, "instagram")
                
                if success:
                    return True, "دانلود با موفقیت انجام شد! ✅"
                else:
                    return False, f"خطا در دانلود: {result}"
                    
            except Exception as e:
                return False, f"خطا در پردازش اطلاعات: {str(e)}"
                
        except Exception as e:
            return False, f"خطا: {str(e)}"
    
    # تابع دانلود یوتیوب با API ساده
    def download_youtube(url):
        try:
            yt = YouTube(url)
            
            # انتخاب بهترین کیفیت
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            
            if not stream:
                return False, "ویدیو قابل دانلود نیست"
            
            download_path = get_download_path()
            filename = f"youtube_{yt.video_id}.mp4"
            file_path = os.path.join(download_path, filename)
            
            # دانلود
            stream.download(output_path=download_path, filename=filename)
            
            # اسکن برای گالری
            scan_file(file_path)
            return True, "دانلود یوتیوب با موفقیت انجام شد! ✅"
            
        except Exception as e:
            return False, f"خطا در دانلود یوتیوب: {str(e)}"
    
    # توابع دانلود (مانند قبل)
    def start_instagram_download(e):
        if insta_url_field.value:
            insta_progress_bar.visible = True
            insta_progress_bar.value = 0.1
            insta_status_text.value = "در حال پردازش لینک... ⏳"
            page.update()
            
            def download_thread():
                try:
                    success, message = download_instagram(insta_url_field.value)
                    
                    if success:
                        insta_progress_bar.value = 1.0
                        insta_status_text.value = message
                    else:
                        insta_progress_bar.value = 0
                        insta_status_text.value = message
                        
                    page.open(ft.SnackBar(ft.Text(value=message)))
                        
                except Exception as e:
                    insta_progress_bar.value = 0
                    insta_status_text.value = f"خطای ناشناخته: {str(e)} ❌"
                    page.open(ft.SnackBar(ft.Text(value=f"خطا: {str(e)}")))
                finally:
                    page.update()
            
            threading.Thread(target=download_thread, daemon=True).start()
        else:
            insta_status_text.value = "لطفا لینک را وارد کنید ❌"
            page.update()

    def start_youtube_download(e):
        if youtube_url_field.value:
            youtube_progress_bar.visible = True
            youtube_progress_bar.value = 0.1
            youtube_status_text.value = "در حال پردازش... ⏳"
            page.update()

            def download_thread():
                try:
                    success, message = download_youtube(youtube_url_field.value)

                    if success:
                        youtube_progress_bar.value = 1.0
                        youtube_status_text.value = message
                    else:
                        youtube_progress_bar.value = 0
                        youtube_status_text.value = message
                        
                    page.open(ft.SnackBar(ft.Text(value=message)))
                        
                except Exception as e:
                    youtube_progress_bar.value = 0
                    youtube_status_text.value = f"خطای ناشناخته: {str(e)} ❌"
                    page.open(ft.SnackBar(ft.Text(value=f"خطا: {str(e)}")))
                finally:
                    page.update()
                    
            threading.Thread(target=download_thread, daemon=True).start()
        else:
            youtube_status_text.value = "لطفا لینک را وارد کنید ❌"
            page.update()

    # المان‌های صفحه اینستاگرام (همان استایل قبلی)
    insta_url_field = ft.TextField(
        label="لینک پست یا ویدیو",
        hint_text="https://www.instagram.com/p/...",
        width=page.width * 0.85,
        border_color="#FFFFFF",
        text_align=ft.TextAlign.RIGHT,
        content_padding=ft.padding.all(12),
        prefix_icon=ft.Icons.LINK
    )
    
    insta_progress_bar = ft.ProgressBar(
        value=0,
        width=page.width * 0.8,
        height=20,
        color="#E1306C",
        bgcolor="#FFFFFF",
        visible=False
    )
    
    insta_status_text = ft.Text(
        "لینک پست را وارد کنید",
        size=16,
        color="#FFFFFF",
        text_align=ft.TextAlign.CENTER
    )
    
    insta_download_button = ft.ElevatedButton(
        content=ft.Text("شروع دانلود", size=16, color="#FFFFFF"),
        bgcolor="#E1306C",
        width=page.width * 0.8,
        height=50,
        on_click=start_instagram_download,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
    )
    
    # صفحه اینستاگرام
    instagram_page = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color="#FFFFFF",
                        icon_size=24,
                        on_click=go_to_main
                    ),
                    ft.Text("دانلود از اینستاگرام", size=20, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    ft.Container(width=40)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=ft.padding.symmetric(vertical=20, horizontal=16),
                bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.BLACK)
            ),
            
            ft.Container(
                content=ft.Column([
                    ft.Container(height=20),
                    ft.Container(
                        content=ft.Image(
                            src=INSTAGRAM_ICON,
                            width=80,
                            height=80,
                        ),
                        padding=ft.padding.all(10),
                        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                        border_radius=40,
                        margin=ft.margin.only(bottom=20)
                    ),
                    ft.Text("لینک مورد نظر خود را وارد کنید", size=16, color="#FFFFFF", text_align=ft.TextAlign.CENTER),
                    ft.Container(height=20),
                    insta_url_field,
                    ft.Container(height=20),
                    insta_download_button,
                    ft.Container(height=30),
                    insta_progress_bar,
                    ft.Container(height=15),
                    insta_status_text,
                    ft.Container(
                        content=ft.Column([
                            ft.Text("راهنمای استفاده:", size=14, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                            ft.Text("• لینک پست یا ویدیو را کپی کنید", size=12, color="#FFFFFF"),
                            ft.Text("• روی دکمه دانلود کلیک کنید", size=12, color="#FFFFFF"),
                            ft.Text("• فایل در پوشه Download ذخیره می‌شود", size=12, color="#FFFFFF"),
                        ], spacing=8),
                        padding=ft.padding.all(16),
                        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                        border_radius=12,
                        margin=ft.margin.symmetric(horizontal=20, vertical=20),
                        width=page.width * 0.9
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                expand=True
            )
        ], spacing=0),
        gradient=ft.LinearGradient(colors=["#667eea", "#764ba2"]),
        expand=True
    )
    
    # المان‌های صفحه یوتیوب
    youtube_url_field = ft.TextField(
        label="لینک ویدیو",
        hint_text="https://www.youtube.com/...",
        width=page.width * 0.85,
        border_color="#FFFFFF",
        text_align=ft.TextAlign.RIGHT,
        content_padding=ft.padding.all(12)
    )
    
    youtube_progress_bar = ft.ProgressBar(
        value=0,
        width=page.width * 0.8,
        height=20,
        color="#FF0000",
        bgcolor="#FFFFFF",
        visible=False
    )
    
    youtube_status_text = ft.Text(
        "لینک ویدیو را وارد کنید",
        size=16,
        color="#FFFFFF",
        text_align=ft.TextAlign.CENTER
    )
    
    youtube_download_button = ft.ElevatedButton(
        content=ft.Text("شروع دانلود", size=16, color="#FFFFFF"),
        bgcolor="#FF0000",
        width=page.width * 0.8,
        height=50,
        on_click=start_youtube_download,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
    )
    
    # صفحه یوتیوب
    youtube_page = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color="#FFFFFF",
                        icon_size=24,
                        on_click=go_to_main
                    ),
                    ft.Text("دانلود از یوتیوب", size=20, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    ft.Container(width=40)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=ft.padding.symmetric(vertical=20, horizontal=16),
                bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.BLACK)
            ),
            
            ft.Container(
                content=ft.Column([
                    ft.Container(height=20),
                    ft.Container(
                        content=ft.Image(
                            src=YOUTUBE_ICON,
                            width=80,
                            height=80,
                        ),
                        padding=ft.padding.all(10),
                        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                        border_radius=40,
                        margin=ft.margin.only(bottom=20)
                    ),
                    ft.Text("لینک مورد نظر خود را وارد کنید", size=16, color="#FFFFFF", text_align=ft.TextAlign.CENTER),
                    ft.Container(height=20),
                    youtube_url_field,
                    ft.Container(height=20),
                    youtube_download_button,
                    ft.Container(height=30),
                    youtube_progress_bar,
                    ft.Container(height=15),
                    youtube_status_text,
                    ft.Container(
                        content=ft.Column([
                            ft.Text("راهنمایی", size=14, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                            ft.Text("• لینک ویدیو را از اپ یوتیوب کپی کنید", size=12, color="#FFFFFF"),
                            ft.Text("• لینک باید با https:// شروع شود", size=12, color="#FFFFFF"),
                            ft.Text("• نسخه بهینه‌شده به زودی...", size=12, color="#FFFF00"),
                        ], spacing=8),
                        padding=ft.padding.all(16),
                        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                        border_radius=12,
                        margin=ft.margin.symmetric(horizontal=20, vertical=20),
                        width=page.width * 0.9
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                expand=True
            )
        ], spacing=0),
        gradient=ft.LinearGradient(colors=["#667eea", "#764ba2"]),
        expand=True
    )
    
    # -------------------- صفحه اصلی --------------------
    header = ft.Container(
        content=ft.Column([
            ft.Text("دانلودر حرفه‌ای", size=24, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ft.Text("دانلود آسان و سریع از یوتیوب و اینستاگرام", size=14, color="#FFFFFF", text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        padding=ft.padding.symmetric(vertical=20, horizontal=10),
        alignment=ft.alignment.center
    )
    
    instagram_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Image(src=INSTAGRAM_ICON, width=25, height=25),
                ft.Text("اینستاگرام", size=18, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ], spacing=12),
            ft.Container(height=8),
            ft.Text("دانلود عکس، ویدیو و استوری از اینستاگرام", size=13, color="#FFFFFF", text_align=ft.TextAlign.CENTER),
            ft.Container(height=12),
            ft.Container(
                content=ft.Text("انتخاب کنید", size=14, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                bgcolor="#E1306C",
                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                border_radius=20,
                alignment=ft.alignment.center,
                width=120,
                on_click=go_to_instagram
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.all(16),
        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
        border_radius=12,
        margin=ft.margin.symmetric(horizontal=16, vertical=8),
        blur=ft.Blur(8, 8, ft.BlurTileMode.MIRROR),
        border=ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.WHITE)),
        width=page.width * 0.9
    )
    
    youtube_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Image(src=YOUTUBE_ICON, width=25, height=25),
                ft.Text("یوتیوب", size=18, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ], spacing=12),
            ft.Container(height=8),
            ft.Text("دانلود ویدیو و موزیک از یوتیوب", size=13, color="#FFFFFF", text_align=ft.TextAlign.CENTER),
            ft.Container(height=12),
            ft.Container(
                content=ft.Text("انتخاب کنید", size=14, color="#FFFFFF", weight=ft.FontWeight.BOLD),
                bgcolor="#FF0000",
                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                border_radius=20,
                alignment=ft.alignment.center,
                width=120,
                on_click=go_to_youtube
            )
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.all(16),
        bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
        border_radius=12,
        margin=ft.margin.symmetric(horizontal=16, vertical=8),
        blur=ft.Blur(8, 8, ft.BlurTileMode.MIRROR),
        border=ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.WHITE)),
        width=page.width * 0.9
    )
    
    footer = ft.Container(
        content=ft.Text("سریع • امن • رایگان", size=12, color="#FFFFFF", weight=ft.FontWeight.BOLD),
        padding=ft.padding.all(16),
        alignment=ft.alignment.center
    )
    
    main_column = ft.Column([
        header,
        instagram_card,
        youtube_card,
        footer
    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    
    main_container = ft.Container(
        content=main_column,
        gradient=ft.LinearGradient(colors=["#667eea", "#764ba2"]),
        expand=True,
        padding=ft.padding.only(bottom=20)
    )
    
    page.add(main_container)

if __name__ == "__main__":
    ft.app(target=main)