import httpx

async def telnyx_cmd(call_control_id, command, api_key, body=None):
    url = f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/{command}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json=body)
