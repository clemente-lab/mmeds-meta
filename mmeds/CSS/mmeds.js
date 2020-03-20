function openStudyAction(evt, cityName) {
    let i, tablinks;
    let x = document.getElementsByClassName("study-action");
    for (i = 0; i < x.length; i++) {
        x[i].style.display = "none";
    }
    document.getElementById(cityName).style.display = "block";
    tablinks = document.getElementsByClassName("action-link");
    for (i = 0; i < x.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" w3-blue", "");
    }
    document.getElementById(cityName).style.display = "block";
    evt.currentTarget.className += " w3-blue";
}

let button = document.getElementById("newID");
let container = document.getElementById("IDcontainer");
let count = [0, 0, 0];
function generate_ID() {
    let specimen = document.getElementById("specimen").value;
    count[specimen] += 1;
    button.innerHTML = "Specimen_" + specimen + "_" + count[specimen];
    container.style.display = "block";
};

// Get the Sidebar
let mySidebar = document.getElementById("mySidebar");

// Get the DIV with overlay effect
let overlayBg = document.getElementById("myOverlay");

// Toggle between showing and hiding the sidebar, and add overlay effect
function w3_open() {
    if (mySidebar.style.display === 'block') {
        mySidebar.style.display = 'none';
        overlayBg.style.display = "none";
    } else {
        mySidebar.style.display = 'block';
        overlayBg.style.display = "block";
    }
}

// Close the sidebar with the close button
function w3_close() {
    mySidebar.style.display = "none";
    overlayBg.style.display = "none";
}
