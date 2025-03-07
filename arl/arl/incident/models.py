
from django.db import models

from arl.user.models import Employer, Store


class Incident(models.Model):
    injuryorillness = models.BooleanField(default=False)
    environmental = models.BooleanField(default=False)
    regulatory = models.BooleanField(default=False)
    economicdamage = models.BooleanField(default=False)
    reputation = models.BooleanField(default=False)
    security = models.BooleanField(default=False)
    fire = models.BooleanField(default=False)

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='incidents')
    brief_description = models.CharField(max_length=30, default='')
    eventtimeline = models.TextField(default='')
    eventdetails = models.TextField()
    eventdate = models.DateField(null=True)
    eventtime = models.TimeField(null=True)
    reportedby = models.CharField(max_length=255, blank=True)
    reportedbynumber = models.CharField(max_length=255, blank=True)

    suncoremployee = models.BooleanField(default=False)
    contractor = models.BooleanField(default=False)
    associate = models.BooleanField(default=False)
    generalpublic = models.BooleanField(default=False)
    staff = models.BooleanField(default=False)
    othertext = models.CharField(blank=True)

    actionstaken = models.TextField()
    correctiveactions = models.TextField(blank=True)

    sno = models.BooleanField(default=False)
    syes = models.BooleanField(default=False)
    scomment = models.CharField(blank=True)

    rna = models.BooleanField(default=False)
    rno = models.BooleanField(default=False)
    ryes = models.BooleanField(default=False)
    rcomment = models.CharField(blank=True)

    gas = models.BooleanField(default=False)
    diesel = models.BooleanField(default=False)
    sewage = models.BooleanField(default=False)
    chemical = models.BooleanField(default=False)
    chemcomment = models.CharField(blank=True)
    deiselexhaustfluid = models.BooleanField(default=False)
    sother = models.BooleanField(default=False)
    s2comment = models.CharField(blank=True)

    air = models.BooleanField(default=False)
    water = models.BooleanField(default=False)
    wildlife = models.BooleanField(default=False)
    land = models.BooleanField(default=False)
    volumerelease = models.CharField(blank=True)

    pyes = models.BooleanField(default=False)
    pno = models.BooleanField(default=False)
    pna = models.BooleanField(default=False)
    pcase = models.CharField(blank=True)

    stolentransactions = models.BooleanField(default=False)
    stoltransactions = models.CharField(blank=True)
    stolencards = models.BooleanField(default=False)
    stolcards = models.CharField(blank=True)
    stolentobacco = models.BooleanField(default=False)
    stoltobacco = models.CharField(blank=True)
    stolenlottery = models.BooleanField(default=False)
    stollottery = models.CharField(blank=True)
    stolenfuel = models.BooleanField(default=False)
    stolfuel = models.CharField(blank=True)
    stolenother = models.BooleanField(default=False)
    stolother = models.CharField(blank=True)
    stolenothervalue = models.CharField(blank=True)
    stolenna = models.BooleanField(default=False)

    gender = models.CharField(max_length=255, blank=True)
    height = models.CharField(max_length=255, blank=True)
    weight = models.CharField(max_length=255, blank=True)
    haircolor = models.CharField(max_length=255, blank=True)
    haircut = models.CharField(max_length=255, blank=True)
    complexion = models.CharField(max_length=255, blank=True)
    beardmoustache = models.CharField(max_length=255, blank=True)
    eyeeyeglasses = models.CharField(max_length=255, blank=True)
    licencenumber = models.CharField(max_length=255, blank=True)
    makemodel = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=255, blank=True)
    scars = models.CharField(max_length=255, blank=True)
    tatoos = models.CharField(max_length=255, blank=True)
    hat = models.CharField(max_length=255, blank=True)
    shirt = models.CharField(max_length=255, blank=True)
    trousers = models.CharField(max_length=255, blank=True)
    shoes = models.CharField(max_length=255, blank=True)
    voice = models.CharField(max_length=255, blank=True)
    bumpersticker = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=255, blank=True)
    damage = models.CharField(max_length=255, blank=True)
    image_folder = models.CharField(max_length=255, null=True)
    user_employer = models.ForeignKey(Employer, on_delete=models.SET_NULL, null=True)

    # Investigation Section
    causalfactors = models.TextField()
    determincauses = models.TextField()
    preventiveactions = models.TextField()

    # Shared Learning Section
    shared_learning_yes = models.BooleanField(default=False)
    shared_learning_no = models.BooleanField(default=False)
    shared_learning_na = models.BooleanField(default=False)
    shared_learning_date = models.DateField(blank=True, null=True)
    shared_learning_method = models.CharField(max_length=255, blank=True, null=True)

    # Emergency Response Plan Actioned by
    emergency_not_applicable = models.BooleanField(default=False)
    emergency_no = models.BooleanField(default=False)
    emergency_site_staff = models.BooleanField(default=False)
    emergency_contractor = models.BooleanField(default=False)
    emergency_public = models.BooleanField(default=False)
    emergency_responders = models.BooleanField(default=False)  # Ex. 911, Fire, Police

    # New fields for email tracking
    queued_for_sending = models.BooleanField(default=False, help_text="Indicates if this file is queued for sending.")
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True, help_text="The timestamp when the file was sent.")
    do_not_send = models.BooleanField(default=False)

    def __str__(self):
        return f"Incident {self.pk}"

    def is_ready_to_send(self):
        """
        Determine if the incident is ready to be sent.
        """
        return self.queued_for_sending and self.sent_at is None


class MajorIncident(models.Model):
    brief_description = models.CharField(max_length=60, default='')
    robbery = models.BooleanField(default=False)
    breakandenter = models.BooleanField(default=False)
    assault = models.BooleanField(default=False)
    bombthreat = models.BooleanField(default=False)
    majorfireorexplosion = models.BooleanField(default=False)
    fatality = models.BooleanField(default=False)
    criticalinjury = models.BooleanField(default=False)

    store = models.ForeignKey(Store, on_delete=models.CASCADE,
                              related_name='majorincidents')
    policeagency = models.CharField(max_length=60, default='', blank=True)
    officerdetails = models.TextField(blank=True)
    eventdate = models.DateField(null=True)
    eventtime = models.TimeField(null=True)
    reportedby = models.CharField(max_length=255, blank=True)
    policefilenumber = models.CharField(max_length=255, blank=True)
    policecalledyes = models.BooleanField(default=False)
    policecalledno = models.BooleanField(default=False)
    policeattendyes = models.BooleanField(default=False)
    policeattendno = models.BooleanField(default=False)

    gsoccalledyes = models.BooleanField(default=False)
    gsoccalledno = models.BooleanField(default=False)

    stolencash = models.BooleanField(default=False)
    stolcash = models.CharField(blank=True)
    stolencards = models.BooleanField(default=False)
    stolcards = models.CharField(blank=True)
    stolentobacco = models.BooleanField(default=False)
    stoltobacco = models.CharField(blank=True)
    stolenlottery = models.BooleanField(default=False)
    stollottery = models.CharField(blank=True)
    stolenother = models.BooleanField(default=False)
    stolother = models.CharField(blank=True)
    stolenothervalue = models.CharField(blank=True)
    stolenna = models.BooleanField(default=False)

    damagetoproperty = models.TextField(blank=True)

    gender = models.CharField(max_length=255, blank=True)
    age = models.CharField(max_length=255, blank=True)
    height = models.CharField(max_length=255, blank=True)
    weight = models.CharField(max_length=255, blank=True)
    haircolor = models.CharField(max_length=255, blank=True)
    haircut = models.CharField(max_length=255, blank=True)
    complexion = models.CharField(max_length=255, blank=True)
    beardmoustache = models.CharField(max_length=255, blank=True)
    eyeeyeglasses = models.CharField(max_length=255, blank=True)
    licencenumber = models.CharField(max_length=255, blank=True)
    makemodel = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=255, blank=True)
    scars = models.CharField(max_length=255, blank=True)
    tatoos = models.CharField(max_length=255, blank=True)
    hat = models.CharField(max_length=255, blank=True)
    shirt = models.CharField(max_length=255, blank=True)
    trousers = models.CharField(max_length=255, blank=True)
    shoes = models.CharField(max_length=255, blank=True)
    voice = models.CharField(max_length=255, blank=True)

    licenceplatenumber = models.CharField(max_length=255, blank=True)
    approximateyearmakemodel = models.CharField(max_length=255, blank=True)
    colour = models.CharField(max_length=255, blank=True)
    distinguishablefeatures = models.CharField(max_length=255, blank=True)
    bumpersticker = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=255, blank=True)
    damage = models.CharField(max_length=255, blank=True)
    image_folder = models.CharField(max_length=255, null=True)
    user_employer = models.ForeignKey(Employer, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"MajorIncident {self.pk}"
