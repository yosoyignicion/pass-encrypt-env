# Modelo de amenazas

## Objetivo
Proteger secretos locales (claves API, tokens) con **contraseña maestra + TOTP**, sin
renunciar a la comodidad cero-prompt durante la sesión de escritorio.

## Activos
- `vault.enc` (cifrado), contraseña maestra, secreto TOTP, clave de recuperación.

## Qué protege

| Amenaza | ¿Mitigado? | Cómo |
|---|---|---|
| Robo del disco / del fichero `vault.enc` | ✅ | AES‑256‑GCM con clave derivada por Argon2id; sin master+TOTP no hay datos |
| Manipulación del fichero | ✅ | AEAD (AES‑GCM) detecta cualquier alteración |
| Alguien sin tu TOTP intenta desbloquear | ✅ | Segundo factor obligatorio; `K2` depende del `totp_secret` |
| Pérdida de master o TOTP | ✅ | Clave de recuperación independiente (K3) |
| Contraseña maestra filtrada en otro sitio | ⚠️ | TOTP evita el acceso salvo que además tengan tu dispositivo |
| Fuerza bruta offline | ✅ | Argon2id (64 MiB, 3 pasadas, 4 lanes) |
| Curioso **en tu misma sesión ya desbloqueada** | ❌ | Precio de la comodidad cero-prompt: el agente tiene las claves en RAM |
| `root` / ptrace / keylogger | ❌ | Indefendible a nivel local |

## Límites conocidos (honestidad)
- El `totp_secret` se guarda **cifrado con K1(master)**: quien tenga la maestra y
  el fichero puede recuperarlo. El TOTP aporta sobre todo **posesión en vivo** del
  dispositivo, no secretismo criptográfico frente a quien ya tiene la maestra.
- Tras desbloquear, el agente sirve secretos a procesos del **mismo UID**. Protege
  contra robo/offline y contra quien no conoce master+TOTP, **no** contra malware
  que ya corre como tú.
- El socket exige el mismo UID (`SO_PEERCRED`), pero no aísla frente a otros
  procesos tuyos.

## Recomendaciones
- Bloquea la bóveda (`passenv lock`) cuando te ausentes.
- Guarda la clave de recuperación **offline**; nunca junto a `vault.enc`.
- `vault.enc` es seguro de subir a tu nube; la clave de recuperación **no**.
