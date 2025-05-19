import time
import os
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import requests
from openai import AsyncOpenAI
from app import create_app, db
from app.models import FitnessCategory, Mapping
import traceback
import asyncio
import json
import logging
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    RetryError,
)
from openai import RateLimitError
from app.services import const, util
from app.services.emag_full_seq import (
    fetch_all_categories_from_categories_list_emag,
    fetch_categories_characteristics_dict,
    fetch_all_emag_products,
    fetch_all_fitness1_products,
    post_emag_product,
)

# Load environment variables from .env file if available
load_dotenv()
openai_api_key = os.environ.get("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=openai_api_key, base_url="https://api.deepseek.com")

logger = logging.getLogger(__name__)


def populate_fitness_categories():
    for cat in const.FITNESS_CATEGORIES:
        # Check if the category already exists
        if not FitnessCategory.query.filter_by(name=cat).first():
            new_cat = FitnessCategory(name=cat)
            db.session.add(new_cat)
            print(f"Adding category: {cat}")
    db.session.commit()
    print("Categories populated successfully.")


def populate_mappings():
    fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    all_fitness1_categories = util.get_current_fitness1_categories(fitness1_products)
    # get a list of the fitness categories names
    emag_categories_names = [cat.name for cat in FitnessCategory.query.all()]

    # Step 6: Build a mapping between Fitness1 and EMAG categories
    categories_mapping = util.build_mapping(
        fitness1_categories=all_fitness1_categories,
        emag_categories=emag_categories_names,
        threshold=80,
        keywords_mapping=const.KEYWORDS_MAPPING,
    )
    mapped_categories_strings = util.map_fitness1_category_to_emag_category_string(
        categories_mapping
    )
    for f1_cat, emag_cat in mapped_categories_strings.items():
        # Check if the mapping already exists
        if (
            not Mapping.query.filter_by(fitness1_category=f1_cat)
            .filter_by(emag_category=emag_cat)
            .first()
        ):
            new_mapping = Mapping(fitness1_category=f1_cat, emag_category=emag_cat)
            db.session.add(new_mapping)
            print(f"Adding mapping: {f1_cat} -> {emag_cat}")
    db.session.commit()
    print("Mappings populated successfully.")


def create_product_name(product: dict) -> str:
    """
    Constructs a name string from product dictionary.
    Only includes non-empty parts to avoid ambiguity.
    """
    parts = [
        product.get("brand_name", ""),
        product.get("product_name", "").replace("|", ""),
        product.get("option", ""),
        product.get("pack", ""),
    ]

    # Filter out empty or None values and strip whitespace
    parts = [part.strip() for part in parts if part and part.strip()]

    return ", ".join(parts)


def update_emag_fitness_products_names():
    # Step 1: Fetch all EMAG products
    print("Starting product update process...")

    # Step 1: Fetch all EMAG products.
    emag_products_result, emag_products_fetched = fetch_all_emag_products(
        api_url=util.build_url(
            base_url=const.EMAG_URL, resource="product_offer", action="read"
        ),
        headers=const.EMAG_HEADERS,
        pause=0,
    )
    if not emag_products_result:
        print("Failed to fetch EMAG products.")
        return {"emag_products_fetched": len(emag_products_fetched)}
    print(f"Fetched {len(emag_products_fetched)} EMAG products.")

    # Step 2: Fetch all Fitness1 products.
    fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    print(f"Fetched {len(fitness1_products)} Fitness1 products.")

    # Step 3: Build mapping between EMAG and Fitness1 products based on EAN.
    emag_p_to_f1_p_map = util.create_emag_p_to_f1_p_map(
        emag_products_fetched, fitness1_products
    )
    print(f"Built mapping for {len(emag_p_to_f1_p_map)} products.")
    updated_emag_product_data = []
    for emag_p_id, f1_p in emag_p_to_f1_p_map:
        # them into the name string
        name_str = create_product_name(f1_p)
        updated_emag_product_data.append(
            {
                "name": name_str,
                "id": emag_p_id,
                "sale_price": f1_p["regular_price"],
                "status": f1_p["available"],
                "vat_id": 6,
            }
        )
    print([emag_p["name"] for emag_p in updated_emag_product_data])

    # Step 5: Split the updated product data into batches.
    batched_updated_emag_product_data = util.split_list(updated_emag_product_data, 50)
    print(
        f"Split updated data into {len(batched_updated_emag_product_data)} batches (batch size: {50})."
    )

    # Step 6: Process each batch and post updates.
    failed_updates = []
    for i, batch in enumerate(batched_updated_emag_product_data):
        print(f"Posting batch {i+1} of {len(batched_updated_emag_product_data)}...")
        time.sleep(1)  # Pause between batches
        response = requests.post(
            url=util.build_url(
                base_url=const.EMAG_URL, resource="product_offer", action="save"
            ),
            json=batch,
            headers=const.EMAG_HEADERS,
        )
        if not response.ok:
            print(
                f"Request failed for batch {i+1} with status code {response.status_code}."
            )
        data = util.EmagResponse(response.json())
        if data.is_error:
            print(f"Batch {i+1} errors: {data.messages} {data.errors}")
            failed_updates.append(
                {
                    "batch": i + 1,
                    "emag_product_data": batch,
                    "messages": data.messages,
                    "errors": data.errors,
                }
            )

    successful_count = len(updated_emag_product_data) - len(failed_updates)
    print(
        f"Update process completed: {successful_count} successful updates, {len(failed_updates)} failed batches."
    )

    # Return a summary dictionary for API consumption.
    return {
        "emag_products_fetched": len(emag_products_fetched),
        "fitness1_products_fetched": len(fitness1_products),
        "updated_entries": len(updated_emag_product_data),
        "successful_updates": successful_count,
        "failed_updates": failed_updates,
    }

    # for mapping in mappings:
    #     emag_category_id = util.get_emag_category_id(mapping.emag_category)
    #     if emag_category_id:
    #         mapping.emag_category_id = emag_category_id
    #         db.session.add(mapping)
    #         print(
    #             f"Updating mapping: {mapping.fitness1_category} -> {mapping.emag_category}"
    #         )


def set_emag_categories_ids():
    # Step 1: Fetch all EMAG products
    emag_products_result, emag_products_fetched = fetch_all_emag_products(
        api_url=util.build_url(
            base_url=const.EMAG_URL, resource="product_offer", action="read"
        ),
        headers=const.EMAG_HEADERS,
    )
    if not emag_products_result:
        print("Failed to fetch EMAG products.")
        return {"emag_products_fetched": len(emag_products_fetched)}
    print(f"Fetched {len(emag_products_fetched)} EMAG products.")

    current_emag_categories = util.get_current_emag_products_categories(
        emag_products_fetched
    )
    all_emag_categories = fetch_all_categories_from_categories_list_emag(
        api_url=util.build_url(
            base_url=const.EMAG_URL, resource="category", action="read"
        ),
        headers=const.EMAG_HEADERS,
        categories_list=current_emag_categories,
    )
    all_fitness_emag_categories = util.get_fitness_related_emag_categories(
        all_emag_categories, const.FITNESS_CATEGORIES
    )
    cat_name_to_id_map = {cat["name"]: cat["id"] for cat in all_fitness_emag_categories}
    print(cat_name_to_id_map)

    # Step 2: Update the FitnessCategory table with EMAG category IDs
    for cat in FitnessCategory.query.all():
        emag_category_id = cat_name_to_id_map.get(cat.name)
        if emag_category_id:
            cat.emag_category_id = emag_category_id
            db.session.add(cat)
            print(f"Updating category: {cat.name} with ID: {emag_category_id}")
    db.session.commit()
    print("Categories IDs updated successfully.")


async def safe_acreate(**kwargs):
    """
    Retries only on RateLimitError (or timeout), up to 5 times;
    reraise any other exception immediately.
    """
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(RateLimitError),
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(5),
        reraise=True,
    ):
        with attempt:
            return await client.chat.completions.create(**kwargs)


async def process_product(
    prod: util.EmagProduct,
    sem: asyncio.Semaphore,
    category: Dict,
    lang: str = "ro",
):
    if lang == "ro":
        language = "Romanian"
    elif lang == "hu":
        language = "Hungarian"
    prd_id = prod.id
    async with sem:
        prd_str = prod.name
        # 1) first API call: translation
        try:
            messages = [
                {
                    "role": "system",
                    "content": f"You are a senior e-commerce localization specialist with native-level Bulgarian and {language}. "
                    + "You know how to preserve marketing tone, structure, and SEO-keywords when translating product metadata. "
                    + "When asked, you also act as a category expert and pick the most relevant product attributes from a given list.",
                },
                {
                    "role": "user",
                    "content": f"Here is a product in Bulgarian. 1) Translate **both** its name and description into {language}.  "
                    + "2) Output exactly this JSON schema and nothing else:\n\n"
                    + "```json\n"
                    + "{\n"
                    + '  "product_name": string,     // the translated name\n'
                    + '  "description": string       // the translated description\n'
                    + "}\n"
                    + "```\n\n"
                    + "Product (BG):\n"
                    + "- Name: “"
                    + prd_str
                    + "”\n"
                    + "- Description: “"
                    + prod.description
                    + "”"
                    "Don't insert literal tabs, newlines or other control characters inside your JSON — if you need one, use the proper JSON escape (\\t, \\n, etc.).",
                },
            ]
            resp1 = await safe_acreate(
                model="deepseek-chat",
                messages=messages,
                stream=False,
                response_format={"type": "json_object"},
                temperature=1.0,
            )
        except RetryError as re:
            # all retries failed on RateLimitError
            logger.error(
                f"[{prd_id}] translation hit rate limit 5×: {re}", exc_info=True
            )
            return None
        except Exception as e:
            # BAD: you saw an AttributeError here
            logger.error(
                f"[{prd_id}] translation unexpected error: {e!r}", exc_info=True
            )
            return None

        # **Inspect** the raw resp1 before you do .choices[0].message.content
        logger.debug(f"[{prd_id}] raw resp1: {resp1!r}")

        # guard against missing attributes
        try:
            text1 = resp1.choices[0].message.content
        except AttributeError as e:
            # maybe resp1.choices[0].message is a dict, not an object
            print("inside AttributeError")
            print("❗️ JSON error:", e)
            print("❗️ Raw text follows\n>>>")
            print(text1)
            print("<<< End raw")
            traceback.print_exc()

            text1 = resp1.choices[0].message.get("content")
            if text1 is None:
                raise

        # parse JSON
        try:
            name_desc = json.loads(text1)
        except json.JSONDecodeError as e:
            # Log full exception + the raw text so you can see what's malformed
            logger.error(
                f"[{prd_id}] JSON parse error at line {e.lineno}, column {e.colno}: {e.msg}\n"
                f"Raw response was:\n{text1!r}",
                exc_info=True,
            )
            traceback.print_exc()
            print(f"[{prd_id}] ❗️ Raw response causing JSONDecodeError:\n{text1!r}\n")
            e.raw = text1
            # Optionally, re-raise or return None so you can skip this one
            return None

        # 2) second API call: characteristics
        try:
            messages.append({"role": "assistant", "content": text1})
            messages.append(
                {
                    "role": "user",
                    "content": """Now, based on the translated product name and description, please review this JSON array of category characteristics and pick the most relevant ones for the product.
                    All characteristics must have have a value, or the documentation later will fail.

        Return **only** a single JSON object matching this schema:

        ```json
        {
        "characteristics": [
            {
            "id": <number>,          // e.g. 6556
            "tag": <string|null>,    // e.g. null
            "value": "<string>"      // e.g. "Barbat" or "Férfi"
            }
        ]
        }
        ```
        Make sure to include the "characteristics" key in the output JSON.""",
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        category["characteristics"], ensure_ascii=False
                    ),
                }
            )
            resp2 = await safe_acreate(
                model="deepseek-chat",
                messages=messages,
                stream=False,
                response_format={"type": "json_object"},
                temperature=1.0,
            )
        except RetryError as re:
            logger.error(
                f"[{prd_id}] characteristics hit rate limit 5x: {re}", exc_info=True
            )
            return None
        except Exception as e:
            logger.error(
                f"[{prd_id}] characteristics unexpected error: {e!r}", exc_info=True
            )
            return None

        logger.debug(f"[{prd_id}] raw resp2: {resp2!r}")

        try:
            text2 = resp2.choices[0].message.content
        except AttributeError:
            text2 = resp2.choices[0].message.get("content")
            if text2 is None:
                raise

        # parse JSON
        try:
            char_json = json.loads(text2)
        except json.JSONDecodeError as e:
            # Log full exception + the raw text so you can see what's malformed
            logger.error(
                f"[{prd_id}] JSON parse error at line {e.lineno}, column {e.colno}: {e.msg}\n"
                f"Raw response was:\n{text2!r}",
                exc_info=True,
            )
            traceback.print_exc()
            print(f"[{prd_id}] ❗️ Raw response causing JSONDecodeError:\n{text2!r}\n")
            e.raw = text2
            # Optionally, re-raise or return None so you can skip this one
            return None

        # set the new name, descrition and characteristics
        prod.name = name_desc["product_name"]
        prod.description = name_desc["description"]
        prod.characteristics = char_json["characteristics"]

        return prod


async def run_process_all(
    emag_products: List[util.EmagProduct],
    all_emag_categories: Dict[int, List[Dict]],
    max_concurrent: int = 100,
    lang: str = "ro",
) -> Tuple[List[Dict], List[Dict]]:
    """
    Given a list of partially built EMAG product objects and the category lookup,
    spin up tasks to translate & pick characteristics, and return the list of
    result-dicts (or None on failure), in the same order.

    Returns a tuple of (translated, failed_products).
    """
    failed_products = []
    translated = []
    sem = asyncio.Semaphore(max_concurrent)
    tasks = []
    for prod in emag_products:
        cat_id = prod.category_id
        category = all_emag_categories.get(cat_id, {})
        tasks.append(asyncio.create_task(process_product(prod, sem, category, lang)))
    all_results = await asyncio.gather(*tasks, return_exceptions=False)
    for prod, res in zip(emag_products, all_results):
        if isinstance(res, Exception):
            # log or retry separately
            print(f"❌ {prod.id} failed: {res}")
            if hasattr(res, "raw"):
                print("   → raw content was:\n", res.raw)
            traceback.print_exception(type(res), res, res.__traceback__)
            failed_products.append(res.to_dict())
        else:
            if res is not None:
                translated.append(res.to_dict())

    print(f"✅ {len(translated)} products processed successfully.")
    if len(translated) > 0:
        print("example translated product:", translated[0])
    print(f"Failed products: {len(failed_products)}.")  # just to see the structure
    if len(failed_products) > 0:
        print("example failed product:", failed_products[0])
    return translated, failed_products


def create_romania_products_initial():
    # Step 1: Fetch all EMAG products
    emag_products_result, emag_products_fetched = fetch_all_emag_products(
        api_url=util.build_url(
            base_url=const.EMAG_URL,
            url_ext="ro",
            resource="product_offer",
            action="read",
        ),
        headers=const.EMAG_HEADERS,
    )
    if not emag_products_result:
        print("Failed to fetch EMAG products.")
        return {"emag_products_fetched": len(emag_products_fetched)}
    print(f"Fetched {len(emag_products_fetched)} EMAG products.")

    # Step 2: Fetch all Fitness1 products
    fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    print(f"Fetched {len(fitness1_products)} Fitness1 products.")

    # Step 3: Determine related EMAG products based on matching EAN (barcode)
    fitness1_related_emag_products = (
        util.get_fitness1_related_emag_products_based_on_ean(
            emag_products_fetched, fitness1_products
        )
    )
    print(
        f"Fetched {len(fitness1_related_emag_products)} Fitness1 related EMAG products."
    )

    # Step 4: Get current EMAG categories from the remaining products
    current_emag_categories = util.get_current_emag_products_categories(
        emag_products_fetched
    )
    print(f"Fetched {len(current_emag_categories)} EMAG categories.")

    # Fetch detailed EMAG category data
    # this is a dict
    # {category_id: characteristics_data}
    all_emag_categories = fetch_categories_characteristics_dict(
        api_url=util.build_url(
            base_url=const.EMAG_URL,
            url_ext="ro",
            resource="category",
            action="read",
        ),
        headers=const.EMAG_HEADERS,
        categories_list=current_emag_categories,
    )
    print(f"Fetched {len(all_emag_categories)} EMAG categories.")
    print(f"Example category data: {list(all_emag_categories.values())[0]!r}.")

    name_to_id = {cat.name: cat.emag_category_id for cat in FitnessCategory.query.all()}
    fitness1_to_emag_id = {
        mapping.fitness1_category: name_to_id.get(mapping.emag_category)
        for mapping in Mapping.query.all()
    }

    # Step 7: Filter Fitness1 products to include only those with a mapped EMAG category
    valid_fitness1_products_data = util.get_fitness1_products_with_mapped_categories(
        fitness1_products, fitness1_to_emag_id
    )
    valid_fitness1_products = [
        util.Fitness1Product.from_dict(product)
        for product in valid_fitness1_products_data
    ]

    # Step 8: Map each Fitness1 product to its corresponding EMAG category data
    # f1_to_emag_categories = util.map_fitness1_category_to_emag_category_data(
    #     mapped_categories_strings, all_fitness_emag_categories
    # )

    # # Get all existing EMAG product IDs (for generating a valid new ID if needed)
    all_emag_product_ids = [product["id"] for product in emag_products_fetched]

    # # Step 9: Create new EMAG products by merging data from Fitness1 with EMAG category info
    emag_products_created = []
    for fitness1_product in valid_fitness1_products:
        emag_product = util.create_emag_product_from_fitness1_product(fitness1_product)
        if emag_product.ean in [
            product["ean"][0] for product in fitness1_related_emag_products
        ]:
            # get the id of the found product and set it to the emag product
            emag_product.id = util.get_emag_product_id_by_ean(
                emag_product.ean, fitness1_related_emag_products
            )
            emag_product.part_number = util.get_emag_part_number_by_ean(
                emag_product.ean, fitness1_related_emag_products
            )
        else:
            emag_product.id = util.get_valid_emag_product_id(all_emag_product_ids)
        emag_product.category_id = fitness1_to_emag_id.get(
            fitness1_product.category, None
        )
        emag_product.part_number = f"IDCARS-{emag_product.id}"
        emag_product.vat_id = 2002

        # Now, create the product name
        name_str = create_product_name(fitness1_product.to_dict())
        # For now, set the name and description to the same string, which will be used for translation
        emag_product.name = name_str
        emag_product.description = name_str
        # Convert the price  from bgn to ron
        from currency_converter import CurrencyConverter

        c = CurrencyConverter()
        emag_product.sale_price = round(
            c.convert(emag_product.sale_price, "BGN", "RON"), 2
        )
        print(
            f"Converted price: {emag_product.sale_price} RON (from {fitness1_product.regular_price} BGN)"
        )

        emag_products_created.append(emag_product)

    print(
        f"Prepared {len(emag_products_created)} EMAG product objects for translation/characteristics."
    )
    updated_emag_products: List[Dict]
    failed_products: List[Dict]
    updated_emag_products, failed_products = asyncio.run(
        run_process_all(emag_products_created, all_emag_categories, lang="ro")
    )
    # save the translated products to a json file
    with open("updated_emag_products.json", "w", encoding="utf-8") as f:
        json.dump(updated_emag_products, f, ensure_ascii=False, indent=4)
    print("Updated products saved to updated_emag_products.json")
    # save the failed products to a json file
    with open("failed_emag_products.json", "w", encoding="utf-8") as f:
        json.dump(failed_products, f, ensure_ascii=False, indent=4)
    print("Failed products saved to failed_emag_products.json")

    print(f"Created {len(emag_products_created)} EMAG product objects.")
    print("example product:", emag_products_created[0])
    print("Example product data:", emag_products_created[0].to_dict())

    # return {
    #     "emag_products_fetched": len(emag_products_fetched),
    #     "emag_products_created": len(emag_products_created),
    #     "emag_products_updated": len(updated_emag_products),
    #     "emag_products_failed": len(failed_products),
    # }

    # # # Step 10: Post the created EMAG products in batches
    # # # Note: The post_emag_product function should already handle splitting into batches.
    # products_data = [product.to_dict() for product in emag_products_created]
    failed_products = post_emag_product(
        emag_product_data=updated_emag_products,
        api_url=util.build_url(
            base_url=const.EMAG_URL,
            url_ext="ro",
            resource="product_offer",
            action="save",
        ),
        headers=const.EMAG_HEADERS,
        batch_size=50,
    )

    successful_count = len(updated_emag_products) - len(failed_products)
    print(
        f"Successfully posted {successful_count} EMAG products, {len(failed_products)} failed."
    )
    # save the failed posted products to a json file
    with open("failed_posted_emag_products.json", "w", encoding="utf-8") as f:
        json.dump(failed_products, f, ensure_ascii=False, indent=4)
    print("Failed posted products saved to failed_posted_emag_products.json")

    # # # Instead of writing to a file, return a summary dictionary
    return {
        "emag_products_fetched": len(emag_products_fetched),
        "fitness1_products_fetched": len(fitness1_products),
        "emag_categories_fetched": len(all_emag_categories),
        "updated_emag_products": len(updated_emag_products),
        "successful_creations": successful_count,
        "failed_products": failed_products,  # List of failed batch details
    }


def create_hungarian_products_initial():
    # Step 1: Fetch all EMAG products
    emag_products_result, emag_products_fetched = fetch_all_emag_products(
        api_url=util.build_url(
            base_url=const.EMAG_URL,
            url_ext="hu",
            resource="product_offer",
            action="read",
        ),
        headers=const.EMAG_HEADERS,
    )
    if not emag_products_result:
        print("Failed to fetch EMAG products.")
        return {"emag_products_fetched": len(emag_products_fetched)}
    print(f"Fetched {len(emag_products_fetched)} EMAG products.")

    # Step 2: Fetch all Fitness1 products
    fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    print(f"Fetched {len(fitness1_products)} Fitness1 products.")

    # Step 3: Determine related EMAG products based on matching EAN (barcode)
    fitness1_related_emag_products = (
        util.get_fitness1_related_emag_products_based_on_ean(
            emag_products_fetched, fitness1_products
        )
    )
    print(
        f"Fetched {len(fitness1_related_emag_products)} Fitness1 related EMAG products."
    )

    # Step 4: Get current EMAG categories from the remaining products
    current_emag_categories = util.get_current_emag_products_categories(
        emag_products_fetched
    )
    print(f"Fetched {len(current_emag_categories)} EMAG categories.")

    # Fetch detailed EMAG category data
    # this is a dict
    # {category_id: characteristics_data}
    all_emag_categories = fetch_categories_characteristics_dict(
        api_url=util.build_url(
            base_url=const.EMAG_URL,
            url_ext="hu",
            resource="category",
            action="read",
        ),
        headers=const.EMAG_HEADERS,
        categories_list=current_emag_categories,
    )
    print(f"Fetched {len(all_emag_categories)} EMAG categories.")
    print(f"Example category data: {list(all_emag_categories.values())[0]!r}.")

    name_to_id = {cat.name: cat.emag_category_id for cat in FitnessCategory.query.all()}
    fitness1_to_emag_id = {
        mapping.fitness1_category: name_to_id.get(mapping.emag_category)
        for mapping in Mapping.query.all()
    }

    # Step 7: Filter Fitness1 products to include only those with a mapped EMAG category
    valid_fitness1_products_data = util.get_fitness1_products_with_mapped_categories(
        fitness1_products, fitness1_to_emag_id
    )
    valid_fitness1_products = [
        util.Fitness1Product.from_dict(product)
        for product in valid_fitness1_products_data
    ]

    # Step 8: Map each Fitness1 product to its corresponding EMAG category data
    # f1_to_emag_categories = util.map_fitness1_category_to_emag_category_data(
    #     mapped_categories_strings, all_fitness_emag_categories
    # )

    # # Get all existing EMAG product IDs (for generating a valid new ID if needed)
    all_emag_product_ids = [product["id"] for product in emag_products_fetched]

    # # Step 9: Create new EMAG products by merging data from Fitness1 with EMAG category info
    emag_products_created = []
    for fitness1_product in valid_fitness1_products:
        emag_product = util.create_emag_product_from_fitness1_product(fitness1_product)
        if emag_product.ean in [
            product["ean"][0] for product in fitness1_related_emag_products
        ]:
            # get the id of the found product and set it to the emag product
            emag_product.id = util.get_emag_product_id_by_ean(
                emag_product.ean, fitness1_related_emag_products
            )
            emag_product.part_number = util.get_emag_part_number_by_ean(
                emag_product.ean, fitness1_related_emag_products
            )
        else:
            emag_product.id = util.get_valid_emag_product_id(all_emag_product_ids)
        emag_product.category_id = fitness1_to_emag_id.get(
            fitness1_product.category, None
        )
        emag_product.part_number = f"IDCARS-{emag_product.id}"
        emag_product.vat_id = 2002

        # Now, create the product name
        name_str = create_product_name(fitness1_product.to_dict())
        # For now, set the name and description to the same string, which will be used for translation
        emag_product.name = name_str
        emag_product.description = name_str
        # Convert the price  from bgn to HUF
        from currency_converter import CurrencyConverter

        c = CurrencyConverter()
        emag_product.sale_price = round(
            c.convert(emag_product.sale_price, "BGN", "HUF"), 2
        )
        print(
            f"Converted price: {emag_product.sale_price} HUF (from {fitness1_product.regular_price} BGN)"
        )

        emag_products_created.append(emag_product)

    print(
        f"Prepared {len(emag_products_created)} EMAG product objects for translation/characteristics."
    )
    updated_emag_products: List[Dict]
    failed_products: List[Dict]
    updated_emag_products, failed_products = asyncio.run(
        run_process_all(emag_products_created, all_emag_categories, lang="hu")
    )
    updated_emag_products = [p for p in updated_emag_products if p is not None]
    failed_products = [p for p in failed_products if p is not None]
    # save the translated products to a json file
    with open("updated_emag_products_hu.json", "w", encoding="utf-8") as f:
        json.dump(updated_emag_products, f, ensure_ascii=False, indent=4)
    print("Updated products saved to updated_emag_products_hu.json")
    # save the failed products to a json file
    with open("failed_emag_products_hu.json", "w", encoding="utf-8") as f:
        json.dump(failed_products, f, ensure_ascii=False, indent=4)
    print("Failed products saved to failed_emag_products_hu.json")

    print(f"Created {len(emag_products_created)} EMAG product objects.")
    print("example product:", emag_products_created[0])
    print("Example product data:", emag_products_created[0].to_dict())

    return {
        "emag_products_fetched": len(emag_products_fetched),
        "emag_products_created": len(emag_products_created),
        "emag_products_updated": len(updated_emag_products),
        "emag_products_failed": len(failed_products),
    }

    # # # Step 10: Post the created EMAG products in batches
    # # # Note: The post_emag_product function should already handle splitting into batches.
    # products_data = [product.to_dict() for product in emag_products_created]
    # failed_products = post_emag_product(
    #     emag_product_data=updated_emag_products,
    #     api_url=util.build_url(
    #         base_url=const.EMAG_URL,
    #         url_ext="hu",
    #         resource="product_offer",
    #         action="save",
    #     ),
    #     headers=const.EMAG_HEADERS,
    #     batch_size=50,
    # )

    # successful_count = len(updated_emag_products) - len(failed_products)
    # print(
    #     f"Successfully posted {successful_count} EMAG products, {len(failed_products)} failed."
    # )
    # # save the failed posted products to a json file
    # with open("failed_posted_emag_products_hu.json", "w", encoding="utf-8") as f:
    #     json.dump(failed_products, f, ensure_ascii=False, indent=4)
    # print("Failed posted products saved to failed_posted_emag_products_hu.json")

    # # # # Instead of writing to a file, return a summary dictionary
    # return {
    #     "emag_products_fetched": len(emag_products_fetched),
    #     "fitness1_products_fetched": len(fitness1_products),
    #     "emag_categories_fetched": len(all_emag_categories),
    #     "updated_emag_products": len(updated_emag_products),
    #     "successful_creations": successful_count,
    #     "failed_products": failed_products,  # List of failed batch details
    # }


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("Running initialize.py...")
        # set_emag_categories_ids()
        # update_emag_fitness_products_names()
        # populate_fitness_categories()
        # populate_mappings()
