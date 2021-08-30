// Dynamic password validation
var myInput = document.getElementById("psw");
var letter = document.getElementById("letter");
var capital = document.getElementById("capital");
var num = document.getElementById("number");
var symbol = document.getElementById("symbol");
var length = document.getElementById("length");

// When the user clicks on the password field, show the message box
myInput.onfocus = function() {
    document.getElementById("message").style.display = "block";
}

// When the user clicks outside of the password field, hide the message box
myInput.onblur = function() {
    document.getElementById("message").style.display = "none";
}

// When the user types something inside the password field
myInput.onkeyup = function() {
    // Validate lowercase letters
    var lowerCaseCharacters = /[a-z]/g;
    if(myInput.value.match(lowerCaseCharacters)) {
        letter.classList.remove("invalid");
        letter.classList.add("valid");
    } else {
        letter.classList.remove("valid");
        letter.classList.add("invalid");
    }
    
    // Validate capital letters
    var upperCaseCharacters = /[A-Z]/g;
    if(myInput.value.match(upperCaseCharacters)) {
        capital.classList.remove("invalid");
        capital.classList.add("valid");
    } else {
        capital.classList.remove("valid");
        capital.classList.add("invalid");
    }

    // Validate numbers 
    var numbers = /[0-9]/g;
    if(myInput.value.match(numbers)) {
        num.classList.remove("invalid");
        num.classList.add("valid");
    } else {
        num.classList.remove("valid");
        num.classList.add("invalid");
    }

    // Validate symbols 
    var symbols = /[!@#$%^&*~`-_+=]/g;
    if(myInput.value.match(symbols)) {
        symbol.classList.remove("invalid");
        symbol.classList.add("valid");
    } else {
        symbol.classList.remove("valid");
        symbol.classList.add("invalid");
    }

    // Validate length 
    if(myInput.value.length >= 10) {
        length.classList.remove("invalid");
        length.classList.add("valid");
    } else {
        length.classList.remove("valid");
        length.classList.add("invalid");
    }
}
