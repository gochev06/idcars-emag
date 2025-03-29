import argparse
import json
import time

import requests

from app.services import const, util


def fetch_all_emag_products(api_url: str, headers: dict, pause: int = 0) -> list:
    """
    Fetches all products from a given API URL with pagination.

    Args:
        api_url (str): The API URL to query.
        headers (dict): The headers to include in the request.
        pause (int, optional): The number of seconds to pause between requests. Defaults to 0.

    Returns:
        list: A list of products fetched from the API.
    """
    page = 1  # starting page
    items_per_page = 100  # number of items per page
    all_products = []

    while True:
        # Set up parameters for pagination
        payload = {"currentPage": page, "itemsPerPage": items_per_page}
        response = requests.post(api_url, json=payload, headers=headers)

        # Check for a successful request
        if response.status_code != 200:
            print(f"Request failed at page {page} with status: {response.status_code}")
            break
        data = response.json()
        if data["isError"]:
            print(
                f"Request failed at page >>{page}<< with messages: {data['messages']} and errors: {data['errors']}"
            )

        # Parse the JSON response
        products = data.get("results", [])
        print(f"Request successful at page {page}")

        # If the products list is empty, we've reached the end
        if not products:
            print(f"No products found on page {page}. Ending pagination.")
            break

        # Append the products from the current page to our total list
        all_products.extend(products)
        print(f"Fetched {len(products)} products from page {page}")

        # Move to the next page
        page += 1
        time.sleep(pause)

    return all_products


def fetch_all_fitness1_products(api_url: str, api_key: str) -> list:
    """
    Fetches all products from a given API URL with a given API key.

    Args:
        api_url (str): The API URL to query.
        api_key (str): The API key to include in the request.

    Returns:
        list: A list of products fetched from the API.
    """
    response = requests.get(api_url, params={"key": api_key, "description": "1"})

    # Check for a successful request
    if response.status_code != 200:
        print(f"Request failed with status code: {response.status_code}")
        return
    data = response.json()
    if data.get("status") not in ["ok"]:
        print(f"Request failed with data {data}")
        return

    return data.get("products")


def fetch_all_categories_from_categories_list_emag(
    api_url: str, headers: dict, categories_list: list, pause: int = 0
) -> list:
    """
    Fetches all categories from a list of category IDs by making API requests.

    Args:
        api_url (str): The API URL to query.
        headers (dict): The headers to include in the request.
        categories_list (list): A list of category IDs to fetch.
        pause (int, optional): The number of seconds to pause between requests. Defaults to 0.

    Returns:
        list: A list of categories fetched from the API.
    """

    all_categories = []

    # Set up parameters for pagination
    for category in categories_list:
        payload = {"id": category}
        response = requests.post(api_url, json=payload, headers=headers)

        # Check for a successful request
        if response.status_code != 200:
            print(
                f"Request failed for category {category} with status: {response.status_code}"
            )
            break
        data = response.json()
        if data["isError"]:
            print(
                f"Request failed for category >>{category}<< with messages: {data['messages']} and errors: {data['errors']}"
            )

        # Parse the JSON response
        category_data = data.get("results", [])
        print(f"Request successful for category {category}")

        # If the products list is empty, we've reached the end
        if not category_data:
            print("No category data found.")
            break

        # Append the products from the current page to our total list
        all_categories.extend(category_data)

        # Move to the next page
        time.sleep(pause)

    print(f"Fetched {len(all_categories)} categories")
    return all_categories


def create_emag_product_from_fields(
    fitness1_product: util.Fitness1Product,
    fitness1_related_emag_products_based_on_ean: list[dict],
    all_emag_product_ids: list[int],
    f1_to_emag_categories: dict,
):
    emag_product = util.create_emag_product_from_fitness1_product(fitness1_product)
    if emag_product.ean in [
        product["ean"][0] for product in fitness1_related_emag_products_based_on_ean
    ]:
        # get the id of the found product and set it to the emag product
        emag_product.id = util.get_emag_product_id_by_ean(
            emag_product.ean, fitness1_related_emag_products_based_on_ean
        )
        emag_product.part_number = util.get_emag_part_number_by_ean(
            emag_product.ean, fitness1_related_emag_products_based_on_ean
        )
    else:
        emag_product.id = util.get_valid_emag_product_id(all_emag_product_ids)
    emag_product.category_id = util.get_emag_category_data_by_fitness1_category(
        f1_to_emag_categories, fitness1_product.category
    ).get("id")
    emag_product.part_number = f"IDCARS-{emag_product.id}"
    return emag_product


def post_emag_product(
    emag_product_data: list[dict], api_url: str, headers: dict, pause=0
):
    batched_emag_products_data = util.split_list(emag_product_data, 50)
    failed_products = []
    for i, batch in enumerate(batched_emag_products_data):

        time.sleep(pause)
        response = requests.post(api_url, json=batch, headers=headers)
        if not response.ok:
            print(f"Request failed with status: {response.status_code}")
        print(response.json())
        data = util.EmagResponse(response.json())

        if data.is_error:
            print(
                f"Request failed >>{batch}<< with messages: {data.messages} and errors: {data.errors}"
            )
            failed_products.append(
                {
                    "batch": i,
                    "emag_product_data": batch,
                    "messages": data.messages,
                    "errors": data.errors,
                }
            )
            # return data

    print(f"Request successful for product {emag_product_data}")
    return failed_products


def run():
    all_emag_products = fetch_all_emag_products(
        api_url=util.build_url(const.EMAG_URL, "product_offer", "read"),
        headers=const.EMAG_HEADERS,
        pause=1,
    )

    print(f"Fetched {len(all_emag_products)} EMAG products")

    all_fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    print(f"Fetched {len(all_fitness1_products)} Fitness1 products")

    fitness1_related_emag_products_based_on_ean = (
        util.get_fitness1_related_emag_products_based_on_ean(
            all_emag_products, all_fitness1_products
        )
    )
    rest_emag_products = [
        emag_product
        for emag_product in all_emag_products
        if emag_product not in fitness1_related_emag_products_based_on_ean
    ]

    current_emag_products_categories = util.get_current_emag_products_categories(
        rest_emag_products
    )

    all_emag_categories = fetch_all_categories_from_categories_list_emag(
        api_url=util.build_url(const.EMAG_URL, "category", "read"),
        headers=const.EMAG_HEADERS,
        categories_list=current_emag_products_categories,
        pause=1,
    )

    all_fitness_emag_categories = util.get_fitness_related_emag_categories(
        all_emag_categories, const.FITNESS_CATEGORIES
    )

    all_fitness1_categories = util.get_current_fitness1_categories(
        all_fitness1_products
    )

    all_emag_categories_names = [
        emag_category["name"] for emag_category in all_fitness_emag_categories
    ]

    categories_mapping = util.build_mapping(
        fitness1_categories=all_fitness1_categories,
        emag_categories=all_emag_categories_names,
        threshold=50,
        keywords_mapping=const.KEYWORDS_MAPPING,
    )
    mapped_categories_strings = util.map_fitness1_category_to_emag_category_string(
        categories_mapping
    )

    valid_fitness1_products_data = util.get_fitness1_products_with_mapped_categories(
        all_fitness1_products, mapped_categories_strings
    )  # used to create emag products
    valid_fitness1_products = [
        util.Fitness1Product.from_dict(product)
        for product in valid_fitness1_products_data
    ]

    f1_to_emag_categories = util.map_fitness1_category_to_emag_category_data(
        mapped_categories_strings, all_fitness_emag_categories
    )
    all_emag_product_ids = [emag_product["id"] for emag_product in all_emag_products]
    emag_products: list[util.EmagProduct] = []
    for fitness1_product in valid_fitness1_products:
        emag_product = create_emag_product_from_fields(
            fitness1_product,
            fitness1_related_emag_products_based_on_ean,
            all_emag_product_ids,
            f1_to_emag_categories,
        )
        emag_products.append(emag_product)
    print(f"Created {len(emag_products)} EMAG products")

    failed_products = post_emag_product(
        emag_product_data=[emag_product.to_dict() for emag_product in emag_products],
        api_url=util.build_url(const.EMAG_URL, "product_offer", "save"),
        headers=const.EMAG_HEADERS,
        pause=2,
    )

    print(f"Created {len(emag_products) - len(failed_products)} EMAG products")
    with open("failed_products.json", "w") as f:
        json.dump(failed_products, f, indent=4)
        print("Failed products saved to failed_products.json")


def update_emag_products():
    all_emag_products = fetch_all_emag_products(
        api_url=util.build_url(const.EMAG_URL, "product_offer", "read"),
        headers=const.EMAG_HEADERS,
        pause=1,
    )

    print(f"Fetched {len(all_emag_products)} EMAG products")

    all_fitness1_products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    print(f"Fetched {len(all_fitness1_products)} Fitness1 products")

    emag_p_to_f1_p_map = util.get_emag_product_id_by_ean(
        all_emag_products, all_fitness1_products
    )

    updated_emag_product_data = util.update_emag_product_data(emag_p_to_f1_p_map)
    batched_updated_emag_product_data = util.split_list(updated_emag_product_data, 50)

    failed_updates = []

    for i, batch in enumerate(batched_updated_emag_product_data):
        time.sleep(2)
        response = requests.post(
            util.build_url(const.EMAG_URL, "product_offer", "save"),
            json=batch,
            headers=const.EMAG_HEADERS,
        )
        if not response.ok:
            print(f"Request failed with status: {response.status_code}")
        print(response.json())
        data = util.EmagResponse(response.json())

        if data.is_error:
            print(
                f"Request failed >>{batch}<< with messages: {data.messages} and errors: {data.errors}"
            )
            failed_updates.append(
                {
                    "batch": i,
                    "emag_product_data": batch,
                    "messages": data.messages,
                    "errors": data.errors,
                }
            )

    print(
        f"Updated {len(updated_emag_product_data) - len(failed_updates)} EMAG products"
    )
    with open("failed_updates.json", "w") as f:
        json.dump(failed_updates, f, indent=4)
        print("Failed updates saved to failed_updates.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CLI for managing EMAG products. Choose to either create new products or update existing ones."
    )
    parser.add_argument(
        "--action",
        choices=["create", "update"],
        required=True,
        help="Specify 'create' to create new products or 'update' to update existing products.",
    )
    args = parser.parse_args()

    if args.action == "create":
        run()
    elif args.action == "update":
        update_emag_products()
