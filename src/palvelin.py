from flask import Flask
import threading
state_lock = threading.Lock()
import atexit

def cleanup():
    print("cleanup func executed!")
    ## meillä ei oo näkyvyyttä täällä mikä on moottoreiden instance
    #  reference, sen pitää selvittää miten homma ratkaistaan myöhemmin
    # sammuta fault poller ja kaikki muutkin apumoduulit

def init():
    atexit.register(cleanup)
    # TODO - käynnistä fault poller moduuli
    # TODO - homee moottorit ja tarkista että se on homattu ja enabloi alternative operation mode
    # kun laittaa position osottamaan siihen missä se on paikallaan, eli kato missä mottori on nyt ja laita analog 
    #modbus cntrl arvo osottamaan siihen kohtaan
    pass # yhistä moottoreihin ja returnaa moottoreiden connection
    # instancet apille joka asettaa ne global variableihin

def create_app():
    app = Flask(__name__)
    # This setup happens only once when the app is created
    # Luodaan tässä houmaus ja global variablejen luonti
    # init() 
    app.is_process_done = True
    print("moi")
    # launch optionit
    
    @app.route('/update_var1', methods=['GET'])
    def update_var1():
        with state_lock: # Varmistaa että tätä state ei muokata eri paikoista samaan aikaan (multi thread safe) s
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

    @app.route("/restart-faultpoller", methods=['GET'])
    def reset_fault_poller():
        # TODO - käynnistä fault poller | Mieti miten launch optioneit vois käyttää tässä
        pass

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(port=5001) ## TODO - tää varmaa tulee launch optioneist???