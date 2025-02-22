// Function to request verification code
function requestVerification(phoneNumber, csrfToken) {
    $.ajax({
        url: twilioVerificationRequestURL,
        type: 'POST',
        data: { 'phone_number': phoneNumber },
        headers: { 'X-CSRFToken': csrfToken },
        success: function (response) {
            if (response.success) {
                handleVerificationCode(phoneNumber, csrfToken);
            } else {
                alert('Failed to request verification code. Please try again.');
            }
        },
        error: function () {
            // Handle error case
        }
    });
}

// Function to check verification code
function handleVerificationCode(phoneNumber, csrfToken) {
    var verificationCode = prompt('Enter the verification code:');
    if (verificationCode) {
        $.ajax({
            url: twilioVerificationCheckURL,
            type: 'POST',
            data: {
                'phone_number': phoneNumber,
                'verification_code': verificationCode
            },
            headers: { 'X-CSRFToken': csrfToken },
            success: function (response) {
                if (response.success) {
                    alert('Phone number verified. Complete the form and click Register');
                    // Disable the phone number input field
                    document.getElementById('phone').disabled = true;
                    document.getElementById('register_button').disabled = false;
                } else {
                    alert('Invalid verification code. Please try again.');
                }
            },
            error: function () {
                // Handle error case
            }
        });
    } else {
        alert('Verification code is required. Please try again.');
    }
}



document.addEventListener('DOMContentLoaded', function () {
    // Initialize the intlTelInput library
    const phoneInputField = document.querySelector("#phone");
    const phoneInput = window.intlTelInput(phoneInputField, {
        utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/19.0.2/js/utils.js",
    });
    // Get the original phone number value from a hidden input field
    const originalPhoneNumber = document.querySelector("#phone-number").value;
    
   
    // Add an event listener to your verify button
    document.getElementById('verify-button').addEventListener('click', function (event) {
        event.preventDefault();
        // Get the phone number with the country code from intlTelInput
        const phoneNumber = phoneInput.getNumber();
        console.log('Verify button clicked!');
        $("#phone-number").val(phoneNumber);
        var isValid = phoneInput.isValidNumber(); // Check if the phone number is valid

        if (isValid) {
            console.log('valid')
             // Your AJAX call to verify the phone number
                const csrftoken = getCookie('csrftoken');
                $.ajax({
                    url: checkPhoneNumberUniqueURL,
                    type: 'POST',
                    data: { 'phone_number': phoneNumber },
                    headers: { 'X-CSRFToken': csrftoken },
                    success: function (response) {
                        // Handle the success response
                        console.log(response);
                        if (response.exists) {
                            // Phone number is not unique, display error message
                            alert('This phone number is already in use.');
                        } else {
                            
                             // Phone number is unique, proceed with Twilio verification
                            requestVerification(phoneNumber, csrftoken);
                        }
                    },
                    error: function (error) {
                        // Handle the error response
                        console.error('Error:', error);
                    }
                });
        }
        else {
            console.log('notvalid')
            alert('This is not a valid phone number')
        }
    });
       

    // Helper function to retrieve the CSRF token from the cookies
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
