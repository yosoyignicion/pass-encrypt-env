# Política de seguridad

`pass-encrypt-env` es una **bóveda local** de secretos. No envía nada a Internet,
no tiene backend remoto ni telemetría. Aun así, los fallos con impacto de seguridad
se gestionan por el canal privado de GitHub.

## Cómo reportar

1. Abre un **aviso privado** en *Security → Report a vulnerability* del repositorio
   (GitHub Security Advisories).
2. Si no puedes, abre un issue **sin detalles explotables** pidiendo contacto.

Incluye: versión/commit, SO, pasos de reproducción, impacto y, si la tienes, una
propuesta de mitigación. **Nunca** adjuntes secretos reales, `vault.enc`, claves de
recuperación ni códigos TOTP; usa datos sintéticos o redactados.

## Alcance

En alcance:

- Debilidades criptográficas: KDF, AEAD, manejo de la DEK, clave de recuperación.
- Fuga de secretos fuera de la bóveda (logs, `bash -x`, core dumps, `/proc`, swap).
- Bypass de la autenticación (maestra + TOTP) o del bloqueo de sesión.
- El socket IPC: acceso de otro UID, o de un proceso no privilegiado que no debería.
- Escritura/lectura de ficheros fuera de los directorios XDG previstos.
- Validación/parsing de `vault.enc` (fichero no confiable).

Fuera de alcance:

- **Un proceso que ya corre con tu mismo UID** mientras la bóveda está desbloqueada:
  es el techo del diseño cero-prompt (ver `docs/THREAT_MODEL.md`).
- Requerir `root`/ptrace/kernel: una vez que `root` controla el equipo, no hay
  defensa local posible.
- Fuerza bruta offline del KDF: se mitiga con Argon2id, no se elimina.

## Principios que protegemos

- **Sin secretos en claro en disco**: la bóveda es AES-256-GCM; el secreto TOTP va
  envuelto. Nunca se escriben valores en claro.
- **Sin red saliente** ni telemetría.
- **Privacidad por defecto**: el agente sirve solo al mismo UID y por un socket `0600`.
- **Endurecimiento del proceso**: `PR_SET_DUMPABLE=0`, sin core dumps, `mlockall`
  best-effort.
- **Sin secretos ni datos personales en el repositorio**, tampoco en los tests.

Gracias por ayudar a mantenerlo seguro.
