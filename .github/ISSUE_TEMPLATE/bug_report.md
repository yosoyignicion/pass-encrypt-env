---
name: Informe de error
about: Algo no funciona como debería
title: "[bug] "
labels: ["bug"]
---

## Descripción
Qué esperabas y qué ocurrió.

## Pasos para reproducir
1. …
2. …

## Entorno
- SO / escritorio: (p. ej. Ubuntu 24.04 + Cinnamon)
- Versión: `passenv --version` (o commit)
- Instalación: `.desktop` / `systemd --user`

## Registro
Salida relevante del agente (`journalctl --user -u passencryptenv-agent -e` o la consola).
**No incluyas secretos, `vault.enc` ni códigos TOTP.**

## Contexto adicional
Cualquier otra pista (¿ocurre con la bóveda bloqueada o desbloqueada?).
