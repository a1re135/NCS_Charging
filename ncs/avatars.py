"""Validated, normalized account avatars stored with the database backup."""
import io
import secrets
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from .db import get_db
from .services import BusinessError

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 25_000_000

def init_avatars(db, backend):
    uid = 'BIGINT UNSIGNED' if backend == 'mysql' else 'INTEGER'
    blob = 'MEDIUMBLOB' if backend == 'mysql' else 'BLOB'
    db.execute(f'''CREATE TABLE IF NOT EXISTS user_avatars (
        user_id {uid} PRIMARY KEY, image_data {blob} NOT NULL, version VARCHAR(32) NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)''' +
        (' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4' if backend == 'mysql' else ''))

def avatar_url(uid):
    row = get_db().execute('SELECT version FROM user_avatars WHERE user_id=?', (uid,)).fetchone()
    return '/api/profile/avatar?v=' + row['version'] if row else None

def normalize_image(data):
    if not data or len(data) > MAX_BYTES:
        raise BusinessError('头像图片不能为空，且不能超过 5 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise BusinessError('请选择 JPG、PNG 或 WebP 图片')
                if image.width * image.height > MAX_PIXELS:
                    raise BusinessError('图片尺寸过大，请选择不超过 2500 万像素的图片')
                image.load()
                image = ImageOps.exif_transpose(image)
                rgba = ImageOps.fit(image.convert('RGBA'), (256,256), method=Image.Resampling.LANCZOS)
                clean = Image.new('RGB', (256,256), '#e8e1fa')
                clean.paste(rgba, mask=rgba.getchannel('A'))
                output = io.BytesIO()
                clean.save(output, format='JPEG', quality=88, optimize=True)
                return output.getvalue()
    except BusinessError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise BusinessError('无法读取图片，请选择完整有效的 JPG、PNG 或 WebP 图片')

def store_avatar(uid, data, backend):
    content = normalize_image(data)
    version = secrets.token_hex(16)
    suffix = ('ON DUPLICATE KEY UPDATE image_data=VALUES(image_data),version=VALUES(version)'
              if backend == 'mysql' else
              'ON CONFLICT(user_id) DO UPDATE SET image_data=excluded.image_data,version=excluded.version')
    get_db().execute('INSERT INTO user_avatars(user_id,image_data,version) VALUES(?,?,?) ' + suffix,
                     (uid,content,version))
    return '/api/profile/avatar?v=' + version
