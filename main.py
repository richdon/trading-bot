from dotenv import load_dotenv
import os

def print_keys():
    # Use a breakpoint in the code line below to debug your script.
    load_dotenv()

    API_KEY = os.getenv("API_KEY")
    SECRET_KEY = os.getenv("SECRET_KEY") # Press ⌘F8 to toggle the breakpoint.
    print(API_KEY, SECRET_KEY)

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_keys()

