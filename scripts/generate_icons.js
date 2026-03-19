#!/usr/bin/env node
/**
 * generate_icons.js — Sivarcasas
 * 
 * Genera todos los íconos necesarios para Android (mipmap-*) y PWA (public/icons/)
 * a partir de un archivo de imagen fuente de alta resolución.
 * 
 * Usa `sharp` que ya es dependencia del proyecto (package.json).
 * 
 * Uso:
 *   node scripts/generate_icons.js <ruta_al_icono_fuente>
 *
 * Ejemplo:
 *   node scripts/generate_icons.js sivarcasaslogo.png
 *   node scripts/generate_icons.js public/logo.webp
 */

const sharp = require('sharp');
const path = require('path');
const fs = require('fs');

const projectRoot = path.join(__dirname, '..');

// Densidades Android → tamaño en px del mipmap
const ANDROID_ICONS = {
  'mipmap-mdpi':    48,
  'mipmap-hdpi':    72,
  'mipmap-xhdpi':   96,
  'mipmap-xxhdpi':  144,
  'mipmap-xxxhdpi': 192,
};

const ANDROID_RES_DIR = path.join(
  projectRoot, 'android', 'app', 'src', 'main', 'res'
);

// Íconos PWA
const PWA_ICONS = {
  'icon-192x192.png': 192,
  'icon-512x512.png': 512,
  'apple-touch-icon.png': 180,
};

const PWA_ICONS_DIR = path.join(projectRoot, 'public', 'icons');

async function resizeAndSave(sourcePath, outputPath, size) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  await sharp(sourcePath)
    .resize(size, size, { fit: 'cover', position: 'centre' })
    .png({ compressionLevel: 9 })
    .toFile(outputPath);

  const rel = path.relative(projectRoot, outputPath);
  console.log(`  ✓ ${rel}  (${size}×${size}px)`);
}

async function main() {
  const sourceArg = process.argv[2];
  if (!sourceArg) {
    console.error('Uso: node scripts/generate_icons.js <ruta_al_icono_fuente>');
    console.error('\nEjemplos:');
    console.error('  node scripts/generate_icons.js sivarcasaslogo.png');
    console.error('  node scripts/generate_icons.js public/logo.webp');
    process.exit(1);
  }

  const sourcePath = path.isAbsolute(sourceArg)
    ? sourceArg
    : path.join(projectRoot, sourceArg);

  if (!fs.existsSync(sourcePath)) {
    console.error(`ERROR: Archivo no encontrado: ${sourcePath}`);
    process.exit(1);
  }

  const meta = await sharp(sourcePath).metadata();
  console.log(`\n📷 Fuente: ${path.basename(sourcePath)} (${meta.width}×${meta.height}px)\n`);

  // Android icons
  console.log('📱 Generando íconos Android...');
  for (const [folder, size] of Object.entries(ANDROID_ICONS)) {
    const resDir = path.join(ANDROID_RES_DIR, folder);
    await resizeAndSave(sourcePath, path.join(resDir, 'ic_launcher.png'), size);
    await resizeAndSave(sourcePath, path.join(resDir, 'ic_launcher_round.png'), size);
    await resizeAndSave(sourcePath, path.join(resDir, 'ic_launcher_foreground.png'), size);
  }

  // PWA icons
  console.log('\n🌐 Generando íconos PWA...');
  for (const [filename, size] of Object.entries(PWA_ICONS)) {
    await resizeAndSave(sourcePath, path.join(PWA_ICONS_DIR, filename), size);
  }

  console.log('\n✅ ¡Todos los íconos generados!');
  console.log('\nPróximo paso: npx cap sync android\n');
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
