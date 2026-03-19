#!/usr/bin/env python3
"""
Script para redimensionar el ícono de Sivarcasas a todos los tamaños
necesarios para Android (densidades mipmap) y para PWA (public/icons/).

Uso:
  python scripts/generate_icons.py <ruta_al_icono_fuente.png>

Requisito: pip install Pillow
"""

import sys
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow no está instalado. Ejecuta: pip install Pillow")
    sys.exit(1)

# Carpeta raíz del proyecto (la carpeta que contiene este script está en scripts/)
PROJECT_ROOT = Path(__file__).parent.parent

# Tamaños necesarios para Android (carpeta mipmap → tamaño en px)
ANDROID_ICONS = {
    "mipmap-mdpi":    48,
    "mipmap-hdpi":    72,
    "mipmap-xhdpi":   96,
    "mipmap-xxhdpi":  144,
    "mipmap-xxxhdpi": 192,
}

ANDROID_RES_DIR = PROJECT_ROOT / "android" / "app" / "src" / "main" / "res"

# Tamaños para PWA (carpeta public/icons/)
PWA_ICONS = {
    "icon-192x192.png": 192,
    "icon-512x512.png": 512,
    "apple-touch-icon.png": 180,
}

PWA_ICONS_DIR = PROJECT_ROOT / "public" / "icons"


def resize_and_save(source: Image.Image, output_path: Path, size: int):
    """Redimensiona la imagen fuente al tamaño dado (cuadrado) y la guarda."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resized = source.resize((size, size), Image.LANCZOS)
    resized.save(output_path, format="PNG", optimize=True)
    print(f"  ✓ {output_path.relative_to(PROJECT_ROOT)}  ({size}x{size}px)")


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/generate_icons.py <ruta_al_icono_fuente.png>")
        print("\nEjemplo:")
        print("  python scripts/generate_icons.py sivarcasaslogo.png")
        sys.exit(1)

    source_path = Path(sys.argv[1])
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path

    if not source_path.exists():
        print(f"ERROR: No se encontró el archivo fuente: {source_path}")
        sys.exit(1)

    print(f"\n📷 Cargando imagen fuente: {source_path.name}")
    source = Image.open(source_path).convert("RGBA")
    print(f"   Tamaño original: {source.width}x{source.height}px")

    # ── Android icons ──────────────────────────────────────────────
    print("\n📱 Generando íconos para Android...")
    for folder, size in ANDROID_ICONS.items():
        ic_launcher_path      = ANDROID_RES_DIR / folder / "ic_launcher.png"
        ic_launcher_round_path = ANDROID_RES_DIR / folder / "ic_launcher_round.png"
        ic_launcher_fg_path   = ANDROID_RES_DIR / folder / "ic_launcher_foreground.png"
        resize_and_save(source, ic_launcher_path, size)
        resize_and_save(source, ic_launcher_round_path, size)
        resize_and_save(source, ic_launcher_fg_path, size)

    # ── PWA icons ──────────────────────────────────────────────────
    print("\n🌐 Generando íconos PWA...")
    for filename, size in PWA_ICONS.items():
        pwa_path = PWA_ICONS_DIR / filename
        resize_and_save(source, pwa_path, size)

    print("\n✅ ¡Todos los íconos generados exitosamente!\n")
    print("Próximo paso: ejecuta 'npx cap sync android' para sincronizar con Android Studio.")


if __name__ == "__main__":
    main()
