# Guía de uso

## Requisitos
Linux con escritorio GTK (probado en Cinnamon/GNOME/X11). Necesitas:

```bash
sudo apt install python3-gi python3-cryptography python3-click python3-qrcode libsecret-tools
```

## Instalación

```bash
git clone https://github.com/yosoyignicion/pass-encrypt-env
cd pass-encrypt-env
./install.sh            # autostart por .desktop (recomendado)
# o:
./install.sh --systemd  # servicio systemd --user (auto-reinicio y logs)
```

`install.sh` enlaza `passenv`, `passenv-agent` y `passenv-load` en `~/.local/bin`.

## Primera vez: crear la bóveda

```bash
passenv init
```

1. Escribe tu **contraseña maestra** dos veces.
2. Escanea el **QR** con tu app de autenticación (Aegis, Google Authenticator…).
3. **Guarda la clave de recuperación offline** (se muestra una sola vez).

La bóveda se guarda en `~/.config/pass-encrypt-env/vault.enc` (`0600`).

## Uso diario

Al iniciar sesión, 5 s después aparece el pop-up. Introduce maestra + TOTP una vez:
el resto de la sesión es **cero-prompt**.

```bash
passenv status                 # estado del agente y de la bóveda
passenv lock                   # borrar las claves de la memoria del agente
passenv set OPENAI_API_KEY     # guarda (pide el valor de forma oculta)
passenv get OPENAI_API_KEY
passenv list
passenv rm  OPENAI_API_KEY
passenv exec -- ./mi-app       # ejecuta con los secretos en el entorno
eval "$(passenv export)"       # inyecta en la shell actual
passenv change-master          # rotar la contraseña maestra
```

### Integración con proyectos (cero-prompt)
`passenv-load` sirve los secretos a un wrapper y cae al *fallback* solo si la bóveda
no tiene esas claves:

```bash
eval "$(passenv-load ruta/.secrets)"   # .secrets: líneas "servicio CLAVE"
passenv exec -- npm run dev
```

## Recuperación y backup

```bash
passenv backup ~/nube/vault.enc        # la bóveda YA está cifrada: es seguro subirla
passenv restore ~/nube/vault.enc       # restaura desde un backup
```

- Si olvidas la maestra o el TOTP: `passenv restore` + la **clave de recuperación**.
  La restauración con recovery se hace reintroduciendo la clave en el flujo de
  desbloqueo (ver `docs/THREAT_MODEL.md`).
- **La clave de recuperación nunca va junto a `vault.enc`.** Guárdala en papel o en
  un gestor distinto.

## systemd vs .desktop

| | `.desktop` (defecto) | `systemd --user` |
|---|---|---|
| Entorno gráfico | garantizado | depende de `DISPLAY` importado |
| Auto-reinicio | no | sí (`Restart=on-failure`) |
| Logs | consola/pop-up | `journalctl --user -u passencryptenv-agent` |

Instala uno u otro; `install.sh` desactiva el otro automáticamente.

## Solución de problemas

- **«Contraseña incorrecta» al pegar la maestra**: los gestores a veces copian con un
  salto de línea final. Versiones antiguas lo conservaban; desde la 1.0.0 la entrada
  se sanea. Asegúrate de pegar solo el texto.
- **«Código TOTP inválido»**: comprueba la hora del móvil (NTP). Se acepta ±60 s.
- **Las apps no ven los secretos**: `passenv status`; si está bloqueada, ábrela con
  `passenv unlock`. `passenv-load` avisa por `stderr` cuando no hay fuente.
- **El pop-up no aparece**: ¿es entorno gráfico? Para systemd, verifica que
  `systemctl --user show-environment | grep DISPLAY` tenga valor.
