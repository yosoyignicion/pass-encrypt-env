# Roadmap

## Pendiente de seguridad (acción del propietario)
- [ ] **Rotar `OPENCODE_API_KEY`** en el panel de OpenCode (se filtró un fragmento
      durante una sesión de verificación). Tras rotarla: `passenv set OPENCODE_API_KEY`.
- [ ] **Revocar el PAT antiguo** asociado a `AssetShrink` (estuvo embebido en el remote).

## Corto plazo
- [ ] **Auto-lock opcional**: bloquear la bóveda al bloquear la pantalla o por
      inactividad (`fase 2`: `org.gnome.ScreenSaver` / `loginctl` + `GLib` idle).
- [ ] **Completions de shell** para `passenv` (bash/zsh/fish) vía `click`.
- [ ] `passenv add` interactivo para importar claves de un `.env`.

## Medio plazo
- [ ] **Recuperación guiada en el pop-up**: botón «usar clave de recuperación» que
      pide la clave y re-enrola TOTP + maestra.
- [ ] **Rotación de TOTP** (`passenv totp rotate`) y multi-dispositivo.
- [ ] Empaquetado `.deb` y `.desktop` con `Icon=` apuntando al logo instalado.

## Largo plazo
- [ ] Soporte **macOS/Windows** del núcleo (Keychain/DPAPI como caché de sesión).
- [ ] Firma de releases y `SHA256SUMS` publicados.
- [ ] Integración con `git-credential-passenv` para servir tokens de Git desde la bóveda.

## No objetivos
- Sincronización en la nube con servidor propio: la bóveda cifrada ya es subible.
- Defensa frente a `root`/malware con tu mismo UID: fuera de alcance por diseño
  (ver `docs/THREAT_MODEL.md`).
