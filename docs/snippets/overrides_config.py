import asyncio

from piighost.config import load_pipeline

pipeline = load_pipeline("piighost.toml")


async def main():
    result = await pipeline.anonymize(
        "Mail public@corp.com or alice@example.com about ACME-FALCON."
    )
    print(result.text)
    # Mail public@corp.com or <<EMAIL:1>> about <<CODENAME:1>>.


asyncio.run(main())
