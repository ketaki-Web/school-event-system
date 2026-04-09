// ===== ALERT MESSAGE FUNCTIONS =====

// Event Registration
function showRegisterAlert() {
alert("You have successfully registered for this event!");
}

// Comment Submission
function showCommentAlert() {
alert("Your comment has been submitted successfully!");
}

// Account Registration
function showAccountAlert() {
alert("Your account has been created successfully!");
}

// Event Creation (Teacher)
function showCreateEventAlert() {

let toastElement = document.getElementById('eventToast');
let toast = new bootstrap.Toast(toastElement);
toast.show();

}

// Event Suggestion (Student)
function showSuggestionAlert() {
alert("Your event suggestion has been submitted!");
}


// Navbar shadow on scroll

window.addEventListener("scroll", function(){
let navbar = document.querySelector(".navbar");

if(window.scrollY > 50){
navbar.style.boxShadow = "0 5px 20px rgba(0,0,0,0.2)";
} else {
navbar.style.boxShadow = "none";
}
});


// Delete confirmation

function confirmDelete() {

let result = confirm("Are you sure you want to delete this event?");

if(result){

let toastElement = document.getElementById('deleteToast');
let toast = new bootstrap.Toast(toastElement);
toast.show();

}

}

// update

function showUpdateEventToast() {

let toastElement = document.getElementById('updateToast');
let toast = new bootstrap.Toast(toastElement);
toast.show();


}

// student toast 

function showStudentToast(message) {

let toastElement = document.getElementById("studentToast");
let toastMessage = document.getElementById("toastMessage");

if(toastElement && toastMessage){

toastMessage.innerText = message;

let toast = new bootstrap.Toast(toastElement);
toast.show();

}

}


// login 
function registerAndRedirect(){

showStudentToast("✅ Account created successfully! Please login.");

setTimeout(function(){
window.location.href = "login.html";
}, 1500);

}


// result 
function showResultToast(){

let toastElement = document.getElementById("resultToast");

if(toastElement){
let toast = new bootstrap.Toast(toastElement);
toast.show();
}

}


function toggleFields(type){

    let nameField = document.getElementById("nameField");
    let groupName = document.getElementById("groupName");
    let membersField = document.getElementById("membersField");

    document.getElementById("individualFields").style.display = "none";
    document.getElementById("groupFields").style.display = "none";

    // remove all required first
    nameField.required = false;
    groupName.required = false;
    membersField.required = false;

    if(type === "individual"){
        document.getElementById("individualFields").style.display = "block";

        nameField.required = true;   // ✅ must fill name
    }

    else if(type === "group"){
        document.getElementById("groupFields").style.display = "block";

        groupName.required = true;   // ✅ must fill
        membersField.required = true;
    }

}


