function initTabs() {
    // Check if any tab is already selected
    if ($("input[name='tab']:checked").length === 0) {
        $("input[name='tab']:first").prop("checked", true);
    }

    // Load the selected tab's form
    loadForm($("input[name='tab']:checked").data("form-url"));

    // Switching between tabs
    $("input[name='tab']").on("change", function () {
        var formUrl = $(this).data("form-url");
        loadForm(formUrl);
    });

    function loadForm(url) {
        $.ajax({
          url: url,
          method: "GET",
          success: function (response) {
            $("#form-container").html(response);
      
            // Re-initialize dropdowns after new HTML is added
            var dropdownTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="dropdown"]'));
            dropdownTriggerList.map(function (dropdownTriggerEl) {
              return new bootstrap.Dropdown(dropdownTriggerEl);
            });
          },
          error: function (xhr, status, error) {
            console.error("Error loading form:", status, error);
          }
        });
      }
}