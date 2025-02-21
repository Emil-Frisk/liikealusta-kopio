from flask import Flask
import threading
state_lock = threading.Lock()
import atexit


def cleanup():
    print("cleanup func executed!")
    ## meillä ei oo näkyvyyttä täällä mikä on moottoreiden instance
    #  reference, sen pitää selvittää miten homma ratkaistaan myöhemmin

def init():
    atexit.register(cleanup)
    pass # yhistä moottoreihin ja returnaa moottoreiden connection
    # instancet apille joka asettaa ne global variableihin

def create_app():
    app = Flask(__name__)
    # This setup happens only once when the app is created
    # Luodaan tässä houmaus ja global variablejen luonti
    # init() 
    app.is_process_done = True
    print("moi")
    
    @app.route('/update_var1', methods=['GET'])
    def update_var1():
        with state_lock: # Varmistaa että tätä state ei muokata eri paikoista samaan aikaan (multi thread safe)
            # Access and modify shared state
            app.is_process_done = False
        return f"Updated var1 to {app.is_process_done}"

    @app.route('/read_var1', methods=['GET'])
    def read_var1():
        with state_lock:
            # Access shared state for reading
            value = app.is_process_done
        return f"Current value of var1 is {value}"
    
    @app.route('/stop', methods=['GET'])
    def stop_motors():
        pass # sammuta moottorit -> päivitä global var?

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(port=5001) ## TODO - tää varmaa tulee launch optioneist???