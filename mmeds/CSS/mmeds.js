function openStudyAction(evt, studyAction) {
    let i, tablinks;
    let x = document.getElementsByClassName("study-action");
    for (i = 0; i < x.length; i++) {
        x[i].style.display = "none";
    }
    document.getElementById(studyAction).style.display = "block";
    tablinks = document.getElementsByClassName("action-link");
    for (i = 0; i < x.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" w3-blue", "");
    }
    document.getElementById(studyAction).style.display = "block";
    evt.currentTarget.className += " w3-blue";
}

let button = document.getElementById("newID");
let container = document.getElementById("IDcontainer");
let count = [0, 0, 0];
function generateID() {
    let specimen = document.getElementById("specimen").value;
    count[specimen] += 1;
    button.innerHTML = "Specimen_" + specimen + "_" + count[specimen];
    container.style.display = "block";
}

// Get the Sidebar
let mySidebar = document.getElementById("mySidebar");

// Get the DIV with overlay effect
let overlayBg = document.getElementById("myOverlay");

// Toggle between showing and hiding the sidebar, and add overlay effect
function w3Open() {
    if (mySidebar.style.display === 'block') {
        mySidebar.style.display = 'none';
        overlayBg.style.display = "none";
    } else {
        mySidebar.style.display = 'block';
        overlayBg.style.display = "block";
    }
}

// Close the sidebar with the close button
function w3Close() {
    mySidebar.style.display = "none";
    overlayBg.style.display = "none";
}

/* 
 * Dynamic pasword validation
 */
let myInput = document.getElementById("psw");
let myInput2 = document.getElementById("psw2");
let letter = document.getElementById("letter");
let capital = document.getElementById("capital");
let num = document.getElementById("num");
let symbol = document.getElementById("symbol");
let length = document.getElementById("length");
let match = document.getElementById("match");

// When the user clicks outside of the password field, hide the message box
if(myInput != null) {
    myInput.onkeyup = function() {
        // Validate lowercase letters
        var lowerCaseCharacters = /[a-z]/g;
        if(myInput.value.match(lowerCaseCharacters)) {
            letter.classList.remove("invalid");
            letter.classList.add("valid");
        } else {
            letter.classList.remove("valid");
            letter.classList.add("invalid")
        }
        
        // Validate lowercase letters
        var upperCaseCharacters = /[A-Z]/g;
        if(myInput.value.match(upperCaseCharacters)) {
            capital.classList.remove("invalid");
            capital.classList.add("valid");
        } else {
            capital.classList.remove("valid");
            capital.classList.add("invalid")
        }

        // Validate lowercase letters
        var numbers = /[0-9]/g;
        if(myInput.value.match(numbers)) {
            num.classList.remove("invalid");
            num.classList.add("valid");
        } else {
            num.classList.remove("valid");
            num.classList.add("invalid")
        }

        // Validate lowercase letters
        var symbols = /[!@#$%^&*~`_+=-]/g;
        if(myInput.value.match(symbols)) {
            symbol.classList.remove("invalid");
            symbol.classList.add("valid");
        } else {
            symbol.classList.remove("valid");
            symbol.classList.add("invalid")
        }

        // Validate lowercase letters
        if(myInput.value.length >= 10) {
            length.classList.remove("invalid");
            length.classList.add("valid");
        } else {
            length.classList.remove("valid");
            length.classList.add("invalid")
        }
    }

    myInput2.onkeyup = function() {
        // Validate matching passwords
        if(myInput.value === myInput2.value) {
            match.classList.remove("invalid");
            match.classList.add("valid");
        } else {
            match.classList.remove("valid");
            match.classList.add("invalid");
        }
    }
}
// Password validation end

// Cookie compliancy begin
// Cookies notification based on 
//      https://html-online.com/articles/cookie-warning-widget-with-javascript/
function GetCookie(name) {
    var arg=name+"=";
    var alen=arg.length;
    var clen=document.cookie.length;
    var i=0;
    while (i<clen) {
        var j=i+alen;
        if (document.cookie.substring(i,j)==arg)
            return "here";
        i=document.cookie.indexOf(" ",i)+1;
        if (i==0) break;
    }
    return null;
}

function testFirstCookie() {
    var visit=GetCookie("cookieCompliancyAccepted");
    if (visit==null) {
        $("#myCookieConsent").fadeIn(400);   // Show warning
    } else {
                // Already accepted
    }        
}

$(document).ready(function(){
    $("#cookieButton").click(function(){
        console.log('Understood');
        var expire=new Date();
        expire=new Date(expire.getTime()+7776000000); // Check again after 90 days
        document.cookie="cookieCompliancyAccepted=here; expires="+expire+";path=/";
      $("#myCookieConsent").hide(400);
    });
    testFirstCookie();
});
// Cookie Compliancy END
