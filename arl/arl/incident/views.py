
from django.shortcuts import render, redirect
from .forms import SectionOneForm, SectionTwoForm  # Import your SectionOneForm
from django.views import View


class MultiSectionFormView(View):
    template_name = 'incident/multi_section_form.html'

    def get(self, request, section=1):
        form1 = SectionOneForm()
        form2 = SectionTwoForm()
        # form1 = form2 = None  # Handle invalid section number here

        context = {'form1': form1, 'form2': form2, 'section': section}
        return render(request, self.template_name, context)

    def post(self, request, section=None):
        if section == 1:
            form1 = SectionOneForm(request.POST)
            form2 = None
        elif section == 2:
            form1 = None
            form2 = SectionTwoForm(request.POST)
        else:
            form1 = form2 = None  # Handle invalid section number here

        if form1 and form1.is_valid():
            # Process section 1 data and redirect to section 2
            return redirect('multi_section_form', section=2)
        elif form2 and form2.is_valid():
            # Process section 2 data and perform final submission
            return redirect('multi_section_form')

        context = {'form1': form1, 'form2': form2, 'section': section}
        return render(request, self.template_name, context)
