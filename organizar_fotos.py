import sys
import os
import shutil
from datetime import datetime
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFileDialog, QLabel, QVBoxLayout, QCheckBox, QComboBox, QTextEdit, QHBoxLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt, QThread, Signal, QMutex, QMutexLocker
from PySide6.QtGui import QPixmap
from PIL import Image
from PIL.ExifTags import TAGS

class OrganizerThread(QThread):
    log_signal = Signal(str)  # Para actualizar la interfaz con logs
    preview_signal = Signal(str)  # Para actualizar la vista previa

    def __init__(self, source_folder, dest_folder, method, copy_files):
        super().__init__()
        self.source_folder = source_folder
        self.dest_folder = dest_folder
        self.method = method
        self.copy_files = copy_files
        self.stop_flag = False
        self.mutex = QMutex()

    def run(self):
        """Ejecuta la organización de archivos en un hilo separado."""
        if not self.source_folder or not self.dest_folder:
            self.log_signal.emit("⚠️ Debes seleccionar una carpeta de origen y destino.")
            return

        for root, _, files in os.walk(self.source_folder):
            for filename in files:
                file_path = os.path.join(root, filename)

                if self.check_stop_flag():
                    self.log_signal.emit("⏹️ Organización detenida.")
                    return

                if not os.path.isfile(file_path):
                    continue

                if not self.is_image(file_path) and not self.is_video(file_path):
                    continue  # Ignorar archivos no compatibles

                # Mostrar vista previa de la imagen actual
                self.preview_signal.emit(file_path)

                photo_date = self.get_photo_date(file_path)
                dest_path = self.generate_dest_path(photo_date, filename)

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                try:
                    if self.copy_files:
                        shutil.copy2(file_path, dest_path)
                        self.log_signal.emit(f"✅ Copiada: {filename} -> {dest_path}")
                    else:
                        shutil.move(file_path, dest_path)
                        self.log_signal.emit(f"✅ Movida: {filename} -> {dest_path}")
                except Exception as e:
                    self.log_signal.emit(f"❌ Error moviendo {filename}: {str(e)}")

        self.log_signal.emit("🎉 Organización completada.")

    def check_stop_flag(self):
        """Verifica si se ha solicitado detener el proceso."""
        with QMutexLocker(self.mutex):
            return self.stop_flag

    def stop(self):
        """Solicita detener la ejecución del hilo de forma segura."""
        with QMutexLocker(self.mutex):
            self.stop_flag = True

    def is_image(self, file_path):
        return os.path.splitext(file_path)[1].lower() in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic"}

    def is_video(self, file_path):
        return os.path.splitext(file_path)[1].lower() in {".mp4", ".mov", ".avi", ".mkv", ".flv"}

    def get_photo_date(self, photo_path):
        """Obtiene la fecha de la foto usando metadatos EXIF o la fecha de modificación."""
        try:
            with Image.open(photo_path) as img:
                exif_data = img._getexif()
                if exif_data:
                    for tag, value in exif_data.items():
                        if TAGS.get(tag, tag) == "DateTimeOriginal":
                            return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
        return datetime.fromtimestamp(os.path.getmtime(photo_path))

    def generate_dest_path(self, photo_date, filename):
        """Genera la ruta de destino según la opción seleccionada."""
        if self.method == "Año/Mes":
            return os.path.join(self.dest_folder, str(photo_date.year), f"{photo_date.month:02d}", filename)
        elif self.method == "Año/Mes/Día":
            return os.path.join(self.dest_folder, str(photo_date.year), f"{photo_date.month:02d}", f"{photo_date.day:02d}", filename)
        else:
            return os.path.join(self.dest_folder, "Evento_Personalizado", filename)

class PhotoOrganizerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Organizador de Fotos")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()
        self.source_label = QLabel("Carpeta de origen: No seleccionada")
        self.dest_label = QLabel("Carpeta de destino: No seleccionada")

        self.btn_select_source = QPushButton("Seleccionar Carpeta de Origen")
        self.btn_select_dest = QPushButton("Seleccionar Carpeta de Destino")

        self.organize_method = QComboBox()
        self.organize_method.addItems(["Año/Mes", "Año/Mes/Día", "Evento Personalizado"])

        self.copy_mode = QCheckBox("Copiar en lugar de mover")
        self.start_button = QPushButton("Iniciar Organización")
        self.stop_button = QPushButton("Detener Organización")
        self.stop_button.setEnabled(False)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        self.image_preview = QGraphicsView()
        self.scene = QGraphicsScene(self)
        self.image_preview.setScene(self.scene)

        layout.addWidget(self.source_label)
        layout.addWidget(self.btn_select_source)
        layout.addWidget(self.dest_label)
        layout.addWidget(self.btn_select_dest)
        layout.addWidget(self.organize_method)
        layout.addWidget(self.copy_mode)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(QLabel("Vista previa:"))
        layout.addWidget(self.image_preview)
        layout.addWidget(QLabel("Registro:"))
        layout.addWidget(self.log_box)

        self.setLayout(layout)

        self.source_folder = ""
        self.dest_folder = ""
        self.organizing_thread = None

        self.btn_select_source.clicked.connect(self.select_source_folder)
        self.btn_select_dest.clicked.connect(self.select_dest_folder)
        self.start_button.clicked.connect(self.start_organization)
        self.stop_button.clicked.connect(self.stop_organization)

    def select_source_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Origen")
        if folder:
            self.source_folder = folder
            self.source_label.setText(f"Carpeta de origen: {folder}")

    def select_dest_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Destino")
        if folder:
            self.dest_folder = folder
            self.dest_label.setText(f"Carpeta de destino: {folder}")

    def start_organization(self):
        self.log_box.clear()
        method = self.organize_method.currentText()
        copy_files = self.copy_mode.isChecked()

        self.organizing_thread = OrganizerThread(self.source_folder, self.dest_folder, method, copy_files)
        self.organizing_thread.log_signal.connect(self.log_box.append)
        self.organizing_thread.preview_signal.connect(self.show_image_preview)
        self.organizing_thread.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_organization(self):
        if self.organizing_thread:
            self.organizing_thread.stop()

    def show_image_preview(self, image_path):
        pixmap = QPixmap(image_path)
        self.scene.clear()
        self.scene.addPixmap(pixmap)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PhotoOrganizerApp()
    window.show()
    sys.exit(app.exec())
