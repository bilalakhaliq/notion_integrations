import os
import time
import requests
from notion_client import Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load environment variables (ensure you have NOTION_KEY and NOTION_DATABASE_ID set)
NOTION_KEY = os.getenv('NOTION_KEY')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

# Initialize the Notion client
notion = Client(auth=NOTION_KEY)

# Create a blank array in which we'll store an object for each pokemon fetched from the PokeAPI
db_pokemon = []

def get_pokemon():
    """
    Fetches Pokémon data from the PokeAPI, processes it, and stores it in db_pokemon.
    """
    # Define start and end variables for the loop below.
    # These numbers correspond to actual Pokemon numbers - e.g. 1 = bulbasaur.
    start = 1
    end = 10  # Change as needed

    # This loop will make the first set of requests to the PokeAPI.
    # We're using a basic for loop because i will correspond to specific Pokemon numbers.
    for i in range(start, end + 1):
        try:
            # Use requests.get() to make a GET request to the PokeAPI's 'pokemon' endpoint.
            # This endpoint allows us to access MOST of the information we need.
            poke = requests.get(f'https://pokeapi.co/api/v2/pokemon/{i}').json()

            # Pokemon have a variable number of types (some have 1, some have 2).
            # The Notion API expects Multi-Select property selections to come in the form of an array of objects,
            # so we need to create an array of objects that we can pass when we're setting the 'Type' Multi-Select property's values.
            types_array = [{"name": t['type']['name']} for t in poke['types']]

            # The PokeAPI returns very basic formatting for Pokemon names - e.g. 'mr-mime'.
            # We want to show names with proper punctuation and capitalization in Notion - e.g. 'Mr. Mime'.
            # This is also important for auto-generating links to Bulbapedia.
            processed_name = poke['species']['name'].split('-')
            processed_name = ' '.join([n.capitalize() for n in processed_name])
            processed_name = (processed_name
                .replace('Mr M', 'Mr. M')
                .replace('Mime Jr', 'Mime Jr.')
                .replace('Mr R', 'Mr. R')
                .replace('mo O', 'mo-o')
                .replace('Porygon Z', 'Porygon-Z')
                .replace('Type Null', 'Type: Null')
                .replace('Ho Oh', 'Ho-Oh')
                .replace('Nidoran F', 'Nidoran♀')
                .replace('Nidoran M', 'Nidoran♂')
                .replace('Flabebe', 'Flabébé')
            )
            
            # Define a variable that holds the bulbapedia URL for the Pokemon.
            # Bulbapedia has a very standardized URL scheme for Pokemon, so all we need to do is pass in the processed_name variable and then replace any space characters it contains with underscores.
            bulb_url = f"https://bulbapedia.bulbagarden.net/wiki/{processed_name.replace(' ', '_')}_(Pokémon)"

            # Here we're defining a variable for the sprite using conditional logic.
            # Certain Gen VIII Pokemon do not have a sprite. The PokeAPI has an 'official-artwork' image for EVERY Pokemon,
            # so we'll set the value of sprite to 'official-artwork' if a 'front_default' sprite doesn't exist.
            sprite = poke['sprites']['front_default'] or poke['sprites']['other']['official-artwork']['front_default']
            artwork = poke['sprites']['other']['official-artwork']['front_default']

            # Now we'll construct the object that will hold all of the data about this Pokemon.
            # We aren't able to pull generation, flavor text, or category from PokeAPI's 'pokemon' endpoint,
            # so we'll add those to this object later.
            poke_data = {
                "name": processed_name,
                "number": poke['id'],
                "types": types_array,
                "height": poke['height'],
                "weight": poke['weight'],
                "hp": poke['stats'][0]['base_stat'],
                "attack": poke['stats'][1]['base_stat'],
                "defense": poke['stats'][2]['base_stat'],
                "special-attack": poke['stats'][3]['base_stat'],
                "special-defense": poke['stats'][4]['base_stat'],
                "speed": poke['stats'][5]['base_stat'],
                "sprite": sprite,
                "artwork": artwork,
                "bulbURL": bulb_url
            }
            # Send a log to the console with each fetched Pokemon's name.
            print(f"Fetched {poke_data['name']}.")
            # Push our poke_data object onto the end of the db_pokemon array.
            db_pokemon.append(poke_data)
            print(db_pokemon[0].keys())
        except Exception as e:
            # If requests.get() fails and throws an error, this except block will catch it and log it in the console.
            print(f"Error fetching Pokémon {i}: {e}")

    # We now need to call another PokeAPI endpoint to get three more pieces of information about each Pokemon:
    # - Flavor text (e.g. "Spits fire that is hot enough to melt boulders. Known to cause forest fires unintentionally.")
    # - Generation (e.g. I, II, III...)
    # - Category (e.g. "Flame Pokemon", "Owl Pokemon")
    # These must be obtained from the pokemon-species endpoint.
    for pokemon in db_pokemon:
        try:
            # Use requests.get() to call the PokeAPI endpoint we want.
            flavor = requests.get(f'https://pokeapi.co/api/v2/pokemon-species/{pokemon["number"]}').json()
            # Find English flavor text. The English-language flavor text might be at any one of the indexes.
            flavor_text = next((entry['flavor_text'].replace('\n', ' ').replace('\f', ' ').replace('\r', ' ')
                                for entry in flavor['flavor_text_entries']
                                if entry['language']['name'] == 'en'), "")
            # Find English category (PokeAPI's term for the category is 'genus').
            category = next((g['genus'] for g in flavor['genera'] if g['language']['name'] == 'en'), "")
            # Generation (e.g. 'generation-i' -> 'I').
            generation = flavor['generation']['name'].split('-')[-1].upper()
            # Add our three new pieces of information to the current pokemon's object.
            pokemon['flavor-text'] = flavor_text
            pokemon['category'] = category
            pokemon['generation'] = generation
            # Add a log entry in the console each time this information is fetched from PokeAPI.
            print(f"Fetched flavor info for {pokemon['name']}.")
        except Exception as e:
            # Log any errors thrown by requests.get(), just as in the previous loop block.
            print(f"Error fetching species info for {pokemon['name']}: {e}")

def sleep(milliseconds):
    """
    Sleep for the given number of milliseconds.
    """
    time.sleep(milliseconds / 1000.0)

def create_pokemon_database(notion, parent_page_id, title="Pokémon Table"):
    """
    Creates a new Notion database with the required Pokémon properties.
    Returns the new database ID.
    """
    db_schema = {
        "Name": {"title": {}},
        "Category": {"rich_text": {}},
        "No": {"number": {}},
        "Type": {"multi_select": {}},
        "Generation": {"select": {}},
        "Sprite": {"files": {}},
        "Height": {"number": {}},
        "Weight": {"number": {}},
        "HP": {"number": {}},
        "Attack": {"number": {}},
        "Defense": {"number": {}},
        "Sp. Attack": {"number": {}},
        "Sp. Defense": {"number": {}},
        "Speed": {"number": {}}
    }
    response = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": title}}],
        properties=db_schema
    )
    print("Created new database with ID:", response["id"])
    return response["id"]

def create_notion_page():
    """
    Sends Pokémon data to Notion, creating a page for each Pokémon in the database.
    """
    # Here's our main loop for the process of sending data to Notion.
    # We already have our array of pokemon objects (db_pokemon), so we can use a for loop to iterate through it.
    for pokemon in db_pokemon:
        # Here we'll construct the data object that we'll send to Notion in order to create a new page.
        # This object defines the database in which the page will live (the "parent") and sets its icon, cover, and property values.
        # It also adds a few blocks to the page's body, including the flavor text and a link to the pokemon's Bulbapedia page.
        data = {
            "parent": {"type": "database_id", "database_id": NOTION_DATABASE_ID},
            "icon": {"type": "external", "external": {"url": pokemon['sprite']}},
            "cover": {"type": "external", "external": {"url": pokemon['artwork']}},
            "properties": {
                "Name": {"title": [{"text": {"content": pokemon['name']}}]},
                "Category": {"rich_text": [{"type": "text", "text": {"content": pokemon['category']}}]},
                "No": {"number": pokemon['number']},
                "Type": {"multi_select": pokemon['types']},
                "Generation": {"select": {"name": pokemon['generation']}},
                "Sprite": {"files": [{"type": "external", "name": "Pokemon Sprite", "external": {"url": pokemon['sprite']}}]},
                "Height": {"number": pokemon['height']},
                "Weight": {"number": pokemon['weight']},
                "HP": {"number": pokemon['hp']},
                "Attack": {"number": pokemon['attack']},
                "Defense": {"number": pokemon['defense']},
                "Sp. Attack": {"number": pokemon['special-attack']},
                "Sp. Defense": {"number": pokemon['special-defense']},
                "Speed": {"number": pokemon['speed']}
            },
            "children": [
                {
                    "object": "block",
                    "type": "quote",
                    "quote": {
                        "rich_text": [{"type": "text", "text": {"content": pokemon['flavor-text']}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": ""}}]}
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": "View This Pokémon's Entry on Bulbapedia:"}}]}
                },
                {
                    "object": "block",
                    "type": "bookmark",
                    "bookmark": {"url": pokemon['bulbURL']}
                }
            ]
        }
        # Here we call our sleep() function, passing it a value of 300 so that the loop "sleeps" for 300ms before going onto the next cycle.
        # This ensures that we respect the Notion API's rate limit of ~3 requests per second.
        sleep(300)
        # Add a log item to the console for our own benefit.
        print(f"Sending {pokemon['name']} to Notion")
        try:
            # Actually create the new page in our Notion database.
            # We call the notion.pages.create() function, which creates a new page in our database.
            # We pass it our data object (defined above), which contains all of the necessary information.
            response = notion.pages.create(**data)
            print(response)
        except Exception as e:
            # Log any errors thrown by the Notion API.
            print(f"Error sending {pokemon['name']} to Notion: {e}")
    # When the entire process is done, this will simply print "Operation Complete" in the console.
    print("Operation complete.")

if __name__ == "__main__":
    # Here's where we actually call the get_pokemon() function. When you type `python notion_pokemon.py` in the Terminal to run this script, it immediately runs this function, which kicks off everything else.
    get_pokemon()
    # Create a new database
    PARENT_PAGE_ID = os.getenv('PARENT_PAGE_ID')  # Replace with your Notion page ID
    new_db_id = create_pokemon_database(notion, PARENT_PAGE_ID)
    NOTION_DATABASE_ID = new_db_id  # Set the variable for use below
    create_notion_page() 
    
    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        sorts=[
            {
                "property": "Name",
                "direction": "descending"
            }
        ]
    )