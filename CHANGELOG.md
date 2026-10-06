# Changelog

Todas las novedades relevantes de **pass-encrypt-env**. Formato basado en
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
[Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

## [1.0.0] - 2026-10-06

Primera versión pública: bóveda local con contraseña maestra + TOTP y agente de
sesión sin prompts.

### Añadido
- **Criptografía**: Argon2id (KDF) + AES-256-GCM (AEAD); clave de datos (DEK)
  envuelta dos veces (master+TOTP y clave de recuperación independiente).
- **Segundo factor TOTP** (RFC 6238) con enrolamiento por QR/URI.
- **Clave de recuperación** de 256 bits en Base32 con checksum, legible y a prueba
  de erratas.
- **Agente de sesión** (`passenv-agent`): mantiene la bóveda en RAM y sirve las
  claves por un socket Unix (`0600`, `SO_PEERCRED`) a procesos del mismo UID.
- **Pop-up GTK3 no modal** al iniciar sesión (5 s tras el login); el escritorio
  sigue usable mientras espera. Icono propio.
- **CLI `passenv`**: `init`, `status`, `unlock`, `lock`, `set`, `get`, `list`, `rm`,
  `env`, `export`, `exec`, `change-master`, `import-keyring`, `backup`, `restore`.
- **Cero-prompt**: `passenv exec -- CMD` y `passenv-load` inyectan el entorno en las
  apps sin volver a pedir la maestra durante la sesión.
- **Endurecimiento**: `PR_SET_DUMPABLE=0`, sin core dumps, `mlockall` best-effort.
- **Instalación**: `install.sh` con autostart `.desktop` (por defecto) o
  `systemd --user` (`--systemd`).

### Corregido
- El pop-up rechazaba la contraseña correcta si se **pegaba** desde un gestor con
  salto de línea/espacio final: ahora se sanea la entrada antes de derivar la clave.
- `passenv-load` ya no depende del `PATH` (usa ruta absoluta) y solo prefiere la
  bóveda si contiene **todas** las claves del manifiesto.

### Seguridad
- Sin secretos en claro en disco; el secreto TOTP va cifrado.
- `vault.enc` a `0600`, directorio a `0700`, socket a `0600`.
- `bin/passenv-load` desactiva `xtrace` para no filtrar valores bajo `bash -x`.
- Modelo de amenazas documentado en `docs/THREAT_MODEL.md`.
