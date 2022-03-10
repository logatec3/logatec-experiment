
var node_locations = [
    [-235,265], // 1
    [-165,265], // 2
    [-235,353], // 3
    [-165,353], // 4
    [-235,441], // 5
    [-165,441], // 6
    [-135,175], // 7
    //[-175,190], 
    [-195,175], // 9
    //[-235,190], 
    [-255,173], // 11
    //[-292,264], 
    [-327,288], // 13
    //[-310,330], 
    [-333,360], // 15
    [-337,408], // 16
    //[-333,433], 
    [-355,478], // 18
    [-435,472], // 19
    [-455,525], // 20
    [-313,538], // 21
    [-203,548], // 22
    [-95 ,530], // 23
    [-95 ,440], // 24
    [-93 ,350], // 25
    [-43 ,198], // 26
    //[-140,490]
];

var node_names = [
    "LGTC51",
    "LGTC52",
    "LGTC53",
    "LGTC54",
    "LGTC55",
    "LGTC56",
    "LGTC57",
    "LGTC58",
    "LGTC59",
    "LGTC60",
    "LGTC61",
    "LGTC62",
    "LGTC63",
    "LGTC64",
    "LGTC65",
    "LGTC66",
    "LGTC67",
    "LGTC68",
    "LGTC69",
    "LGTC70",
    "LGTC71"
]


/**
 * Math
 */
export default class ble_localization {

    constructor() {
        this.P_Tx_dBm = 7.0;
        this.alpha = 3.8;
    }

    WLS_localization(x, y, weights, dist) {
        var z = new Array(x.length).fill(1);
        var w = math.diag(weights);
        var A = [];
        var AT = [];
        var tmp, B;

        A.push(math.multiply(-2.0, x));
        A.push(math.multiply(-2.0, y));
        A.push(z);

        A = math.transpose(math.matrix(A));
        AT = math.transpose(A);

        tmp = math.multiply(AT,w);
        tmp = math.multiply(tmp,A);
        tmp = math.inv(tmp);
        tmp = math.multiply(tmp,AT);
        tmp = math.multiply(tmp, w);

        B = math.multiply(-1, math.add(math.square(x), math.square(y)));
        B = math.add(B, math.square(dist));

        tmp = math.multiply(tmp, B);
        x = tmp._data[0];
        y = tmp._data[1];
        return [x,y,0];
    }

    RSSI_to_distance(rssi){
        var distances = [];
        var d = 0;
        for (let index = 0; index < rssi.length; index++) {
            d = (this.P_Tx_dBm - rssi[index] - 40.05)/(this.alpha*10.0);
            d = math.pow(10.0, d);
            distances.push(d);
        }
        return distances;
    }

    weights_to_locations(weights){
        var x = new Array(weights.length).fill(1);
        var y = new Array(weights.length).fill(1);
        for (let index = 0; index < weights.length; index++) {
            if(weights[index]){
                x[index] = node_locations[index][0];
                y[index] = node_locations[index][1];
            }
        }
        return [x,y];
    }


}

/**
 * Device list with their measurement queues & list of active devices.
 * 
 * queue = [
 *  {device:"LGTC51", data:[1,2,3]},
 *  {device:"LGTC52", data:[1,2,3]},
 *  {device:"LGTC53", data:[]},
 *  .
 *  .
 *  .
 *  {device:"LGTC71", data:[1,2,3]},
 * ]
 * 
 * node_states  = [1, 1, 0, ... , 1]
 */
export class rssi_queue {

    constructor() {
        this.num_of_dev = node_names.length;
        this.queue = [];
        this.node_states = [];
        this.clean();
    }

    // Cleans the queue and list of active devices.
    // Must be called before/after the experiment start/end!
    clean() {
        this.node_states = new Array(this.num_of_dev).fill(0);
        this.queue = new Array(this.num_of_dev).fill(0);
        for(let i=0; i<this.num_of_dev; i++) {
            let q = {device:node_names[i], data:[]};
            this.queue[i] = q;
        }
    }

    // Add measurements to the queue and mark the device as active
    putMeasurement(dev_name, rssi) {
        let index = this.queue.findIndex(m => m.device === dev_name);
        if(index != -1){
            this.queue[index]["data"].push(rssi);
            this.node_states[index] = 1;
        }
        else {
            console.warn("Device with name" + dev_name + " is not suited for this exp.")
        }
    }

    // Get measurements from one device
    getOneMeasurement(dev_name) {
        let index = this.queue.findIndex(m => m.device === dev_name);
        return this.queue[index]["data"];
    }

    // Get all & averaged measurements from the queue
    getAllMeasurements(del = true) {
        let m = new Array(this.num_of_dev).fill(0);

        // Cycle through queue
        for(let i=0; i<this.num_of_dev; i++) {
            let avg = 0;
            let items = this.queue[i]["data"].length;
            // Cycle through items (if there are any)
            if (items != 0){
                for(let j=0; j<items; j++) {
                    avg += this.queue[i]["data"][j];
                }
                avg /= items;
                m[i] = avg;
                // Delete old measurements
                if (del == true) this.queue[i]["data"] = [];
            }
        }
        return m; 
    }

    getActiveDevices() {
        return this.node_states;
    }

    // Debug ... TODO: delete 
    printQueue(){
        console.log(this.queue);
    }
}