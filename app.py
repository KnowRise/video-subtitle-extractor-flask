from flask import (
    Flask,
    send_from_directory,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
import os
import psycopg2
from flask_bcrypt import Bcrypt
import ffmpeg
from waitress import serve

app = Flask(__name__)
app.config["SECRET_KEY"] = "FLASK-Secret-key"
bcrypt = Bcrypt(app)

# Ambil DATABASE_URL dari environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode='require')

# Menentukan folder statis untuk video dan subtitle
app.config["STATIC_FOLDER"] = "static"  # Folder tempat file video dan subtitle


@app.route("/")
def index():
    return '<h1 align="center" style="margin-top:200;">Hello, World!</h1>'


# Endpoint untuk mengakses file video dan subtitle
@app.route("/static/<path:filename>")
def download_file(filename):
    return send_from_directory(app.config["STATIC_FOLDER"], filename)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form["password"]
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM password WHERE id = 1")
        stored_password = cursor.fetchone()[0]
        cursor.close()

        if bcrypt.check_password_hash(stored_password, password):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))

        flash("Password salah!", "error")  # Pesan error jika password salah
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        new_password = request.form["password"]
        hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")

        cursor = conn.cursor()
        cursor.execute("UPDATE password SET password = %s WHERE id = 1", (hashed_password,))
        conn.commit()
        cursor.close()

        return redirect(url_for("logout"))

    return render_template("change_password.html")


def clear_static_folder():
    """Menghapus semua file di folder /static."""
    folder = app.config["STATIC_FOLDER"]
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)


def extract_subtitle(video_path, output_vtt_path):
    """Ekstrak subtitle langsung ke format .vtt."""
    try:
        # Ekstrak subtitle langsung ke .vtt
        ffmpeg.input(video_path).output(output_vtt_path, **{"c:s": "webvtt"}).run(
            overwrite_output=True
        )
        return os.path.exists(output_vtt_path)
    except ffmpeg.Error as e:
        print(f"Error during subtitle extraction: {e}")
        return False


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    video = None
    subtitle = None

    if request.method == "POST":
        # Hapus semua file di folder /static
        clear_static_folder()

        # Ambil file video
        video_file = request.files.get("video")
        subtitle_file = request.files.get("subtitle")

        if not video_file:
            flash("Video wajib diunggah!", "error")
            return redirect(url_for("dashboard"))

        # Simpan video ke folder /static
        video_path = os.path.join(app.config["STATIC_FOLDER"], "video.mp4")
        video_file.save(video_path)
        video = "video.mp4"

        if subtitle_file:
            # Jika subtitle diunggah, cek format dan simpan sebagai .vtt
            subtitle_path = os.path.join(app.config["STATIC_FOLDER"], "subtitle.vtt")
            subtitle_ext = os.path.splitext(subtitle_file.filename)[1].lower()

            if subtitle_ext == ".srt":
                # Konversi .srt ke .vtt
                temp_subtitle_path = os.path.join(
                    app.config["STATIC_FOLDER"], "subtitle.srt"
                )
                subtitle_file.save(temp_subtitle_path)
                ffmpeg.input(temp_subtitle_path).output(
                    subtitle_path, **{"f": "webvtt"}
                ).run(overwrite_output=True)
                os.remove(temp_subtitle_path)  # Hapus file .srt setelah konversi
            elif subtitle_ext == ".vtt":
                subtitle_file.save(
                    subtitle_path
                )  # Simpan langsung jika sudah dalam format .vtt
            subtitle = "subtitle.vtt"
        else:
            # Jika tidak ada subtitle eksternal, coba ekstrak dari video
            subtitle_path = os.path.join(app.config["STATIC_FOLDER"], "subtitle.vtt")
            if extract_subtitle(video_path, subtitle_path):
                subtitle = "subtitle.vtt"

    return render_template("dashboard.html", video=video, subtitle=subtitle)


if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)
