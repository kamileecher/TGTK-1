# -*- coding: utf-8 -*-

import asyncio, aria2p, logging, os
from ..core.getVars import get_val
from telethon.tl.types import KeyboardButtonCallback
from telethon.errors.rpcerrorlist import MessageNotModifiedError
from ..core.status.status import ARTask
from functools import partial

# referenced from public leech
# pylint: disable=no-value-for-parameter
torlog = logging.getLogger(__name__)
aloop = asyncio.get_event_loop()

async def aria_start():
    aria2_daemon_start_cmd = []
    # start the daemon, aria2c command
    aria2_daemon_start_cmd.append("aria2c")
    # aria2_daemon_start_cmd.append("--allow-overwrite=true")
    aria2_daemon_start_cmd.append("--daemon=true")
    aria2_daemon_start_cmd.append("--enable-rpc")
    aria2_daemon_start_cmd.append("--disk-cache=0")
    aria2_daemon_start_cmd.append("--follow-torrent=false")
    aria2_daemon_start_cmd.append("--max-connection-per-server=10")
    aria2_daemon_start_cmd.append("--min-split-size=10M")
    aria2_daemon_start_cmd.append("--rpc-listen-all=true")
    aria2_daemon_start_cmd.append(f"--rpc-listen-port=8100")
    aria2_daemon_start_cmd.append("--rpc-max-request-size=1024M")
    aria2_daemon_start_cmd.append("--seed-ratio=0.0")
    aria2_daemon_start_cmd.append("--seed-time=1")
    aria2_daemon_start_cmd.append("--split=10")
    aria2_daemon_start_cmd.append(f"--bt-stop-timeout=100")
    aria2_daemon_start_cmd.append(f"--max-tries=10")
    aria2_daemon_start_cmd.append(f"--retry-wait=2")
    #
    torlog.debug(aria2_daemon_start_cmd)
    #
    process = await asyncio.create_subprocess_exec(
        *aria2_daemon_start_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    torlog.debug(stdout)
    torlog.debug(stderr)
    arcli = await aloop.run_in_executor(None, partial(aria2p.Client, host="http://localhost", port=8100, secret=""))
    aria2 = await aloop.run_in_executor(None, aria2p.API, arcli)

    return aria2

async def add_magnet(aria_instance, magnetic_link, c_file_name):
    try:
        download = await aloop.run_in_executor(None, aria_instance.add_magnet, magnetic_link)
    except Exception as e:
        return False, "**⛔ FAILED** \n" + str(e) + " \nPlease Don't dd Slow Links. read /help."
    else:
        return True, "" + download.gid + ""


async def add_torrent(aria_instance, torrent_file_path):
    if torrent_file_path is None:
        return False, "**⛔ FAILED** \n\nSomething went wrong while adding <u>Torrent</u> file."
    if os.path.exists(torrent_file_path):
        # Add Torrent Into Queue
        try:

            download = await aloop.run_in_executor(None, partial(aria_instance.add_torrent, torrent_file_path, uris=None, options=None, position=None))

        except Exception as e:
            return False, "**⛔ FAILED** \n" + str(e) + " \nPlease don't add slow links. Read /help."
        else:
            return True, "" + download.gid + ""
    else:
        return False, "**⛔ FAILED** \n" + str(e) + " \nPlease try other sources to get a working link."


async def add_url(aria_instance, text_url, c_file_name):
    uris = [text_url]
    # Add URL Into Queue
    try:
        
        download = await aloop.run_in_executor(None, aria_instance.add_uris, uris)

    except Exception as e:
        return False, "**⛔ FAILED** \n" + str(e) + " \nPlease don't add slow links. Read /help."
    else:
        return True, "" + download.gid + ""

async def check_metadata(aria2, gid):
    file = await aloop.run_in_executor(None, aria2.get_download, gid)
    torlog.info(file)
    if not file.followed_by_ids:
        return None
    new_gid = file.followed_by_ids[0]
    torlog.info("changing GID " + gid + " to " + new_gid)
    return new_gid

async def aria_dl(
    incoming_link,
    c_file_name,
    sent_message_to_update_tg_p,
    user_msg
):
    aria_instance = await aria_start()
    
    ar_task = ARTask(None, sent_message_to_update_tg_p, aria_instance, None)
    await ar_task.set_original_mess()

    if incoming_link.lower().startswith("magnet:"):
        sagtus, err_message = await add_magnet(aria_instance, incoming_link, c_file_name)
    elif incoming_link.lower().endswith(".torrent"):
        #sagtus, err_message = await add_torrent(aria_instance, incoming_link)
        #sagtus, err_message = await add_url(aria_instance, incoming_link, c_file_name)
        await ar_task.set_inactive("Unable to Download .torrent file")
        return False, ar_task
    else:
        sagtus, err_message = await add_url(aria_instance, incoming_link, c_file_name)
    if not sagtus:
        await ar_task.set_inactive(err_message)
        return sagtus, ar_task
        
    torlog.info(err_message)

    await ar_task.set_gid(err_message)

    op = await check_progress_for_dl(
        aria_instance,
        err_message,
        sent_message_to_update_tg_p,
        None,
        ar_task,
        user_msg=user_msg
    )
    if incoming_link.startswith("magnet:"):
        #
        err_message = await check_metadata(aria_instance, err_message)
        #
        await asyncio.sleep(1)
        if err_message is not None:
            op = await check_progress_for_dl(
                aria_instance,
                err_message,
                sent_message_to_update_tg_p,
                None,
                ar_task,
                user_msg=user_msg
            )
        else:
            await ar_task.set_inactive("Unable to get metadata.\n")
            return False, ar_task
    await asyncio.sleep(1)
    
    if op is None:
        await ar_task.set_inactive("Known error. Nothing wrong here. You didnt follow instructions.")
        return False, ar_task
    else:
        statusr, stmsg = op
        if statusr:
            file = await aloop.run_in_executor(None, aria_instance.get_download,err_message)
            to_upload_file = file.name
            await ar_task.set_path(to_upload_file)
            await ar_task.set_done()
            return True, ar_task
        else:
            await ar_task.set_inactive(stmsg)
            return False, ar_task

async def check_progress_for_dl(aria2, gid, event, previous_message, task, rdepth = 0, user_msg=None):
    try:
        file = await aloop.run_in_executor(None, aria2.get_download, gid)
        complete = file.is_complete
        if not complete:
            if not file.error_message:
                msg = ""
                
                await task.refresh_info(file)
                await task.update_message()

                
            else:
                msg = file.error_message
                await event.edit(f"`{msg}`",parse_mode="html", buttons=None)
                torlog.error(f"The aria2 download failed due to: {msg}")
                return False, f"The aria download failed due to: {msg}"
            await asyncio.sleep(get_val("EDIT_SLEEP_SECS"))
            
            # TODO idk not intrested in using recursion here
            return await check_progress_for_dl(
                aria2, gid, event, previous_message,task,user_msg=user_msg
            )
        else:
            await event.edit(f"**Download Successfully👏:** \n\n **File Name📂:** `{file.name}`\n**Total Size⚙️:** (`{file.total_length_string()}`)", buttons=None)
            return True, "Download Complete"
    except aria2p.client.ClientException as e:
        if " not found" in str(e) or "'file'" in str(e):
            fname = "N/A"
            try:
                fname = file.name
            except:pass
            task.cancel = True
            await task.set_inactive()
            return False, f"Download was Canceled. {fname}"
        else:
            torlog.warning("Errored due to a client error.")
        pass
    except MessageNotModifiedError:
        pass
    except RecursionError:
        file.remove(force=True)
        return False, "The link is dead."
    except Exception as e:
        torlog.info(str(e))
        if " not found" in str(e) or "'file'" in str(e):
            return False, "The download has been already cancelled."
        else:
            torlog.warning(str(e))
            return False, f"error: {str(e)}"

async def remove_dl(gid):
    aria2 = await aria_start()
    try:
        downloads = await aloop.run_in_executor(None, aria2.get_download, gid)
        downloads.remove(force=True, files=True)
    except:
        torlog.exception("exc")
        pass
