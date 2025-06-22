    // Check validity of email address
    function is_valid_email(email) {
      var regex = /^\w+([.-]?\w+)*@\w+([.-]?\w+)*(\.\w{2,3})+$/;
      return regex.test(email);
    }
    
    
    // Update the format of cells as a function of booking status
    function show_clicked_bookings() {
      for(var i = 0 ; i<n_cells; i++){
        var c = document.getElementById("Cell" + String(i))
        if(list_selected[i]) {
          if(list_busy[i]) {
            // Selected by the user but already booked
              c.setAttribute("style", "background-color: #ee9999; color: DDDDDD;");
            }
            else {
            // Selected by the user and available
              c.setAttribute("style", "background-color: #dd6666; color: #FFFFFF;");
            }
        } else {
          if(list_busy[i]) {
            // Already booked
            c.setAttribute("style", "background-color: #EEEEEE; color: #BBBBBB;");
    
          } else
          {
            // Not booked nor selected
            c.setAttribute("style", "background-color: #FFFFFF; color: #000000;");
          }
        }
      }
    }
    
    // Make a string describing the selection of bookings, shown concisely
    function get_selection_description() {
      var s = '';
      var first_selected = "";
      var last_selected = "";
      var last_is_selected = false;
      var warnings = "";
      for(var i = 0 ; i<n_cells ; i++) {
        if(list_selected[i]) {
          if(last_is_selected) {
            last_selected = list_dt[i]
          } else {
            last_is_selected = true;
            first_selected = list_dt[i];
            last_selected = list_dt[i];
          }
          if(list_busy[i]>0) {
            warnings += list_dt[i] + " (" + String(list_busy[i]) + "p)  ";
          }
        } else {
          if(last_is_selected) {
            if(last_selected == first_selected) {
              s += last_selected + '<BR>';
            } else {
              s += first_selected + ' → ' + last_selected + '<BR>';
            }
            last_is_selected = false;
          }
        }
      }
      if(s=='') {
        s = '(None)'
      }
      if(warnings != "") {
        s += "\n\n<BR>Attention: ces dates sont déjà prises:  " + warnings;
      }
      return(s)
    }
    
    
    // Update the Web line showing selection description
    function update_selection_description() {
      document.getElementById("DescriptionSelection").innerHTML = get_selection_description();
    }
    
    
    // Define the behaviour of a cell when clicked
    function on_click_cell(tableCell) {
      // Get the number of the  cell that has been clicked
      var cell_num = parseInt(tableCell.id.substring(4, tableCell.id.length),10);
    
      // Change the status of the cell
      list_selected[cell_num] = 1-list_selected[cell_num];
    
      // Update visuals
      show_clicked_bookings();
      update_selection_description();
    }
    
    // Set the callback functions for each cell
    function set_table_click_reaction(){
      for(var i = 0 ; i<n_cells; i++){
        document.getElementById('Cell'+String(i)).onclick = function () {
            on_click_cell(this);
        };
      }
    }
    
    // Show the buttons with number of people staying
    function select_number_people(n) {
      const buttons = document.querySelectorAll("#buttonGridNoSpace button");
      n_people = n;
      buttons.forEach((btn, index) => {
        if (index < n) {
          btn.style.backgroundColor = "#dd6666";
          btn.style.color = "white";
        } else {
          btn.style.backgroundColor = "#eeeeee";
          btn.style.color = "";
        }
      });
    }
    
    // Show error message
    function show_error(s) {
      document.getElementById("error_status").innerHTML = s;
    }
    
    // Function called when the user clicks 'Book'
    function doMakeBooking() {
      // Check user name input
      var user_name = document.getElementById('user_name').value;
      if(user_name.length < 3) {
        show_error("Nom incorrect ou manquant. Veuillez le corriger et soumettre de nouveau");
        return;
      }
    
      // Check user email input
      var user_email = document.getElementById('user_email').value;
      if(user_email.length < 3) {
        show_error("Adresse email incorrecte. Veuillez la corriger et soumettre de nouveau");
        return;
      }
      if(!is_valid_email(user_email)) {
        show_error("Adresse email incorrecte. Veuillez la corriger et soumettre de nouveau");
        return;
      }
    
      // Check number of people for booking
      if(n_people<1) {
        show_error("Le nombre de personnes doit être au moins égal à un. Veuillez corriger le chiffre et soumettre de nouveau");
        return;
      }
    
      // Check number of people for booking
      if(n_people>9) {
        show_error("Le nombre de personnes ne peut pas excéder 9. Veuillez corriger le chiffre et soumettre de nouveau");
        return;
      }
    
      // Check the list of dates selected
      var n_dates = 0;
      var list_date_selected = [];
      for(var i = 0 ; i<n_cells ; i++) {
        if(list_selected[i]) {
            list_date_selected.push(list_dt[i]);
            n_dates += 1;
        }
       }
       if(n_dates<1)  {
           show_error("Au moins une date doit être sélectionnée. Veuillez corriger la sélection et soumettre de nouveau");
           return;
       }
    
      // Submit to server
      var booking_descr = ["Add", user_name, user_email, n_people, list_date_selected];
      show_error('');
    fetch("http://localhost:5050/berger_web_process_new_booking", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ x: booking_descr })
    })
    .then(response => response.text())  
    .then(html => {
        console.log("Response from Python:", html);
        document.open();            
        document.write(html);       
        document.close();         
    })
    .catch(error => {
        console.error("Error calling Python:", error);
    });
   }
    
