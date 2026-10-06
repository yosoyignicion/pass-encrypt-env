"""CLI ``passenv``: gestiona la bóveda y habla con el agente de sesión."""

from __future__ import annotations

import getpass
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import click

from . import __version__, ipc, recovery, totp, vault


# --------------------------------------------------------------------- utilidades
def _vault_path(ctx: click.Context) -> Path:
    return Path(ctx.obj["vault"])


def _agent_launcher(popup: bool) -> list[str]:
    exe = shutil.which("passenv-agent")
    if exe:
        cmd = [exe]
    else:
        src = str(Path(__file__).resolve().parent.parent)
        env_path = os.environ.get("PYTHONPATH", "")
        os.environ["PYTHONPATH"] = f"{src}:{env_path}" if env_path else src
        cmd = [sys.executable, "-m", "pass_encrypt_env.agent"]
    if not popup:
        cmd.append("--no-popup")
    return cmd


def _ensure_agent(popup: bool = False, timeout: float = 8.0) -> bool:
    if ipc.is_agent_running():
        return True
    subprocess.Popen(
        _agent_launcher(popup),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ipc.is_agent_running():
            return True
        time.sleep(0.2)
    return False


def _wait_unlocked(timeout: float | None = None) -> bool:
    if timeout is None:
        try:
            timeout = float(os.environ.get("PASSENV_UNLOCK_TIMEOUT", "120"))
        except ValueError:
            timeout = 120.0
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if ipc.request({"cmd": "status"}, timeout=2).get("unlocked"):
                return True
        except OSError:
            pass
        time.sleep(0.4)
    return False


def _ensure_unlocked() -> None:
    if not _ensure_agent(popup=False):
        raise click.ClickException("no se pudo iniciar el agente passenv-agent")
    if ipc.request({"cmd": "status"}, timeout=2).get("unlocked"):
        return
    click.echo("Bóveda bloqueada: introduce los datos en el pop-up…")
    ipc.request({"cmd": "unlock"}, timeout=5)
    if not _wait_unlocked():
        raise click.ClickException("desbloqueo cancelado o agotado")


def _prompt_master(confirm: bool = False) -> str:
    first = getpass.getpass("Contraseña maestra: ")
    if not first:
        raise click.ClickException("la contraseña maestra no puede estar vacía")
    if confirm:
        again = getpass.getpass("Repite la contraseña maestra: ")
        if first != again:
            raise click.ClickException("las contraseñas no coinciden")
    return first


def _emit_exports(secrets: dict) -> None:
    for key, value in sorted(secrets.items()):
        click.echo(f"export {key}={shlex.quote(value)}")


# -------------------------------------------------------------------------- grupo
@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="passenv")
@click.option(
    "--vault",
    "vault_path",
    default=None,
    help="Ruta de la bóveda (por defecto ~/.config/pass-encrypt-env/vault.enc)",
)
@click.pass_context
def main(ctx: click.Context, vault_path: str | None) -> None:
    """Bóveda local de secretos con contraseña maestra + TOTP."""
    ctx.ensure_object(dict)
    ctx.obj["vault"] = Path(vault_path) if vault_path else vault.default_vault_path()


# --------------------------------------------------------------------- init / totp
@main.command()
@click.option("--force", is_flag=True, help="Sobrescribe una bóveda existente")
@click.pass_context
def init(ctx: click.Context, force: bool) -> None:
    """Crea la bóveda, la contraseña maestra y el segundo factor TOTP."""
    path = _vault_path(ctx)
    if path.exists() and not force:
        raise click.ClickException(f"ya existe una bóveda en {path} (usa --force)")

    master = _prompt_master(confirm=True)
    click.echo("Derivando clave con Argon2id…")
    vault_dict, _unlocked, recovery_raw = vault.create_vault(master)
    vault.save_vault(vault_dict, path)

    secret = _unlocked.totp_secret
    uri = totp.provisioning_uri(secret, account=os.environ.get("USER", "user"))
    click.echo("\nEscanea este código con tu app de autenticación (Aegis, Google Authenticator…):\n")
    try:
        import qrcode

        qrcode.QRCode(border=1).add_data(uri)
        qr = qrcode.QRCode(border=1)
        qr.add_data(uri)
        qr.make()
        qr.print_ascii(invert=True)
    except Exception:  # noqa: BLE001
        click.echo("(no se pudo dibujar el QR)")
    click.echo(f"Secreto TOTP: {totp.secret_b32(secret)}")
    click.echo(f"URI: {uri}")

    click.echo("\n" + "=" * 64)
    click.echo("CLAVE DE RECUPERACIÓN (guárdala OFFLINE, se muestra una sola vez):")
    click.echo("\n  " + recovery.format_recovery_key(recovery_raw) + "\n")
    click.echo("Sin ella, si pierdes la maestra o el TOTP no hay acceso.")
    click.echo("=" * 64)

    click.echo(f"\nBóveda creada en: {path}")
    click.echo("Siguiente: instala el autostart con ./install.sh  (o ejecuta: passenv-agent)")


# ------------------------------------------------------------------------- estado
@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Muestra el estado del agente y de la bóveda."""
    path = _vault_path(ctx)
    click.echo(f"Bóveda: {path}  ({'existe' if path.exists() else 'NO existe'})")
    if not ipc.is_agent_running():
        click.echo("Agente: no en ejecución")
        return
    resp = ipc.request({"cmd": "status"}, timeout=2)
    state = "desbloqueada" if resp.get("unlocked") else "bloqueada"
    click.echo(f"Agente: en ejecución — bóveda {state} ({resp.get('count', 0)} claves)")


@main.command()
def unlock() -> None:
    """Pide el desbloqueo mostrando el pop-up."""
    if not _ensure_agent(popup=False):
        raise click.ClickException("no se pudo iniciar passenv-agent")
    ipc.request({"cmd": "unlock"}, timeout=5)
    if _wait_unlocked():
        click.echo("Bóveda desbloqueada.")
    else:
        raise click.ClickException("desbloqueo cancelado o agotado")


@main.command(name="lock")
def lock_cmd() -> None:
    """Bloquea la bóveda (borra las claves de la memoria del agente)."""
    if not ipc.is_agent_running():
        click.echo("El agente no está en ejecución.")
        return
    ipc.request({"cmd": "lock"}, timeout=2)
    click.echo("Bóveda bloqueada.")


# --------------------------------------------------------------- CRUD de secretos
@main.command(name="list")
def list_cmd() -> None:
    """Lista las claves guardadas."""
    _ensure_unlocked()
    resp = ipc.request({"cmd": "list"})
    for key in resp.get("keys", []):
        click.echo(key)


@main.command()
@click.argument("key")
def get(key: str) -> None:
    """Imprime el valor de una clave."""
    _ensure_unlocked()
    resp = ipc.request({"cmd": "get", "key": key})
    if not resp.get("ok"):
        raise click.ClickException(resp.get("error", "error"))
    click.echo(resp["value"])


@main.command(name="set")
@click.argument("key")
@click.option("--value", default=None, help="Valor (si se omite, se pide de forma oculta)")
def set_(key: str, value: str | None) -> None:
    """Guarda o actualiza una clave."""
    _ensure_unlocked()
    if value is None:
        value = getpass.getpass(f"Valor para {key}: ")
    resp = ipc.request({"cmd": "set", "key": key, "value": value})
    if not resp.get("ok"):
        raise click.ClickException(resp.get("error", "error"))
    click.echo(f"OK: {key} actualizada.")


@main.command()
@click.argument("key")
def rm(key: str) -> None:
    """Elimina una clave."""
    _ensure_unlocked()
    resp = ipc.request({"cmd": "rm", "key": key})
    if not resp.get("ok"):
        raise click.ClickException(resp.get("error", "error"))
    click.echo(f"OK: {key} eliminada." if resp.get("removed") else f"{key} no existía.")


# ------------------------------------------------------------------- export / exec
@main.command()
def export() -> None:
    """Emite líneas 'export K=V' (úsalo con: eval "$(passenv export)")."""
    _ensure_unlocked()
    resp = ipc.request({"cmd": "export"})
    if not resp.get("ok"):
        raise click.ClickException(resp.get("error", "error"))
    _emit_exports(resp.get("secrets", {}))


@main.command(name="env")
@click.option(
    "--if-unlocked",
    "if_unlocked",
    is_flag=True,
    help="No interactúa: sale con código 3 si la bóveda está bloqueada o el agente no corre.",
)
def env_cmd(if_unlocked: bool) -> None:
    """Emite los secretos como 'export K=V' sin bloquear (pensado para wrappers)."""
    if not ipc.is_agent_running():
        if if_unlocked:
            sys.exit(3)
        raise click.ClickException("el agente no está en ejecución")
    resp = ipc.request({"cmd": "export"}, timeout=2)
    if not resp.get("ok"):
        if if_unlocked:
            sys.exit(3)
        _ensure_unlocked()
        resp = ipc.request({"cmd": "export"})
        if not resp.get("ok"):
            raise click.ClickException(resp.get("error", "error"))
    _emit_exports(resp.get("secrets", {}))


@main.command(name="exec", context_settings={"ignore_unknown_options": True})
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def exec_cmd(command: tuple[str, ...]) -> None:
    """Ejecuta un comando con los secretos inyectados en el entorno."""
    args = list(command)
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        raise click.ClickException("uso: passenv exec -- COMANDO [ARGS...]")
    _ensure_unlocked()
    resp = ipc.request({"cmd": "export"})
    if not resp.get("ok"):
        raise click.ClickException(resp.get("error", "error"))
    env = dict(os.environ)
    env.update(resp.get("secrets", {}))
    os.execvpe(args[0], args, env)


# -------------------------------------------------------- mantenimiento de bóveda
@main.command(name="change-master")
@click.pass_context
def change_master(ctx: click.Context) -> None:
    """Cambia la contraseña maestra (mantiene TOTP y DEK)."""
    path = _vault_path(ctx)
    vault_dict = vault.load_vault(path)
    master = getpass.getpass("Contraseña maestra actual: ")
    code = click.prompt("Código TOTP", default="", show_default=False)
    try:
        unlocked = vault.unlock_with_master(vault_dict, master, code)
    except vault.VaultError as exc:
        raise click.ClickException(str(exc)) from exc
    new_master = _prompt_master(confirm=True)
    vault.change_master(vault_dict, unlocked, new_master)
    vault.save_vault(vault_dict, path)
    click.echo("Contraseña maestra actualizada. Vuelve a desbloquear.")


@main.command()
@click.option("--from-keyring", "from_keyring", is_flag=True, help="Importa desde gnome-keyring vía .secrets")
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False), required=False)
def import_keyring(from_keyring: bool, manifest: str | None) -> None:
    """Importa secretos de gnome-keyring (manifiesto '.secrets': 'servicio CLAVE')."""
    if not from_keyring or not manifest:
        raise click.ClickException("uso: passenv import-keyring --from-keyring RUTA/.secrets")
    _ensure_unlocked()
    count = 0
    for raw in Path(manifest).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise click.ClickException(f"línea inválida: {raw!r}")
        service, key = parts
        value = subprocess.run(
            ["secret-tool", "lookup", "service", service, "key", key],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        if not value:
            click.echo(f"  omitida (no está en keyring): {service}/{key}")
            continue
        resp = ipc.request({"cmd": "set", "key": key, "value": value})
        if resp.get("ok"):
            count += 1
            click.echo(f"  importada: {key}")
        else:
            click.echo(f"  error en {key}: {resp.get('error')}")
    click.echo(f"Importadas {count} claves a la bóveda.")


@main.command()
@click.argument("destination", type=click.Path())
@click.pass_context
def backup(ctx: click.Context, destination: str) -> None:
    """Copia la bóveda cifrada a DESTINATION (segura para nube)."""
    src = _vault_path(ctx)
    if not src.exists():
        raise click.ClickException("no existe la bóveda")
    shutil.copy2(src, destination)
    click.echo(f"Copia cifrada guardada en {destination}")
    click.echo("Recuerda: la CLAVE DE RECUPERACIÓN nunca va junto a este archivo.")


@main.command()
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def restore(ctx: click.Context, source: str) -> None:
    """Restaura la bóveda desde un backup cifrado."""
    dst = _vault_path(ctx)
    if dst.exists():
        click.confirm(f"Se sobrescribirá {dst}. ¿Continuar?", abort=True)
    shutil.copy2(source, dst)
    os.chmod(dst, 0o600)
    click.echo(f"Bóveda restaurada en {dst}")


if __name__ == "__main__":
    main()
