from django.db import models

from arl.user.models import Employer, Store


class Incident(models.Model):
    # -------------------------------------------------------------------------
    # Primary incident type
    # -------------------------------------------------------------------------

    injuryorillness = models.BooleanField(default=False)
    environmental = models.BooleanField(default=False)
    regulatory = models.BooleanField(default=False)
    economicdamage = models.BooleanField(default=False)
    reputation = models.BooleanField(default=False)
    security = models.BooleanField(default=False)
    fire = models.BooleanField(default=False)

    # -------------------------------------------------------------------------
    # Section 1 - Incident information
    # -------------------------------------------------------------------------

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="incidents",
    )

    brief_description = models.CharField(
        max_length=30,
        default="",
    )

    eventtimeline = models.TextField(default="")

    eventdetails = models.TextField()

    eventdate = models.DateField(null=True)

    eventtime = models.TimeField(null=True)

    reportedby = models.CharField(
        max_length=255,
        blank=True,
    )

    reportedbynumber = models.CharField(
        max_length=255,
        blank=True,
    )

    # Who reported the incident
    suncoremployee = models.BooleanField(default=False)
    contractor = models.BooleanField(default=False)
    associate = models.BooleanField(default=False)
    generalpublic = models.BooleanField(default=False)
    staff = models.BooleanField(default=False)

    othertext = models.CharField(
        max_length=255,
        blank=True,
    )

    # -------------------------------------------------------------------------
    # Contractor involvement
    #
    # This is separate from "contractor" above.
    # "contractor" means the incident was reported by a contractor.
    # "contractor_involved" means a contractor was involved in the incident.
    # -------------------------------------------------------------------------

    contractor_involved = models.BooleanField(
        null=True,
        blank=True,
        help_text="Was a contractor involved in the incident?",
    )

    contractor_company_name = models.CharField(
        max_length=255,
        blank=True,
    )

    # -------------------------------------------------------------------------
    # Immediate and corrective actions
    # -------------------------------------------------------------------------

    actionstaken = models.TextField()

    correctiveactions = models.TextField(blank=True)

    # -------------------------------------------------------------------------
    # Off-property impact
    #
    # These existing fields are retained exactly as they are currently used.
    # -------------------------------------------------------------------------

    sno = models.BooleanField(default=False)
    syes = models.BooleanField(default=False)

    scomment = models.CharField(
        max_length=255,
        blank=True,
    )

    # -------------------------------------------------------------------------
    # Regulatory authorities
    # -------------------------------------------------------------------------

    rna = models.BooleanField(default=False)
    rno = models.BooleanField(default=False)
    ryes = models.BooleanField(default=False)

    rcomment = models.CharField(
        max_length=255,
        blank=True,
    )

    regulatory_notification_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text=("Reference or case number supplied by the regulatory authority."),
    )

    # -------------------------------------------------------------------------
    # Product spilled
    # -------------------------------------------------------------------------

    gas = models.BooleanField(default=False)
    diesel = models.BooleanField(default=False)
    sewage = models.BooleanField(default=False)
    chemical = models.BooleanField(default=False)

    chemcomment = models.CharField(
        max_length=255,
        blank=True,
    )

    deiselexhaustfluid = models.BooleanField(default=False)

    sother = models.BooleanField(default=False)

    s2comment = models.CharField(
        max_length=255,
        blank=True,
    )

    # -------------------------------------------------------------------------
    # Spill containment
    # -------------------------------------------------------------------------

    spill_contained = models.BooleanField(
        null=True,
        blank=True,
        help_text="Was the spill contained?",
    )

    spill_contained_concrete_asphalt = models.BooleanField(
        default=False,
        help_text="Was the spill contained to concrete or asphalt?",
    )

    spill_contained_oil_water_separator = models.BooleanField(
        default=False,
        help_text="Was the spill contained to the oil-water separator?",
    )

    spill_migrated_offsite = models.BooleanField(
        null=True,
        blank=True,
        help_text="Did the spill migrate offsite?",
    )

    # -------------------------------------------------------------------------
    # Environmental impact
    # -------------------------------------------------------------------------

    air = models.BooleanField(default=False)
    water = models.BooleanField(default=False)
    wildlife = models.BooleanField(default=False)
    land = models.BooleanField(default=False)

    volumerelease = models.CharField(
        max_length=255,
        blank=True,
    )

    # -------------------------------------------------------------------------
    # Significant Security Incident Report - ENMCFM373
    # -------------------------------------------------------------------------

    # Significant Security Incident Type
    security_robbery = models.BooleanField(default=False)
    security_break_and_enter = models.BooleanField(default=False)
    security_assault = models.BooleanField(default=False)
    security_bomb_threat = models.BooleanField(default=False)
    security_major_fire_explosion = models.BooleanField(default=False)
    security_fatality = models.BooleanField(default=False)
    security_critical_injury = models.BooleanField(default=False)

    # Police Information
    #
    # Existing fields:
    #   pyes  -> Police notified: Yes
    #   pno   -> Police notified: No
    #   pna   -> Not applicable
    #   pcase -> Police file number
    #
    police_attended = models.BooleanField(
        null=True,
        blank=True,
        help_text="Did police attend the site?",
    )

    police_agency = models.CharField(
        max_length=255,
        blank=True,
        help_text="Police agency, such as RCMP, OPP, or local police.",
    )

    police_officer_name = models.CharField(
        max_length=255,
        blank=True,
    )

    police_officer_rank = models.CharField(
        max_length=100,
        blank=True,
    )

    police_officer_badge_number = models.CharField(
        max_length=100,
        blank=True,
    )

    # GSOC Notification
    gsoc_called = models.BooleanField(
        null=True,
        blank=True,
        help_text="Was the Global Security Operations Center called?",
    )

    # Theft Details
    #
    # Existing fields can be reused for:
    #   stolentobacco / stoltobacco
    #   stolenlottery / stollottery
    #   stolencards / stolcards
    #   stolenother / stolother / stolenothervalue
    #   stolenna
    #
    theft_cash = models.BooleanField(default=False)

    theft_cash_value = models.CharField(
        max_length=255,
        blank=True,
    )

    # Damage to Property
    #
    # Existing `damage` contains the description.
    #
    damage_value = models.CharField(
        max_length=255,
        blank=True,
    )

    # Additional suspect information
    suspect_age = models.CharField(
        max_length=100,
        blank=True,
    )

    # Optional general clothing description in addition to the existing
    # hat, shirt, trousers, and shoes fields.
    clothing_description = models.CharField(
        max_length=255,
        blank=True,
    )

    # Additional vehicle information
    vehicle_year = models.CharField(
        max_length=100,
        blank=True,
    )

    vehicle_distinguishing_features = models.TextField(
        blank=True,
    )


    # -------------------------------------------------------------------------
    # Police involvement
    # -------------------------------------------------------------------------

    pyes = models.BooleanField(default=False)
    pno = models.BooleanField(default=False)
    pna = models.BooleanField(default=False)

    pcase = models.CharField(
        max_length=255,
        blank=True,
    )

    # -------------------------------------------------------------------------
    # Theft and loss information
    # -------------------------------------------------------------------------

    stolentransactions = models.BooleanField(default=False)

    stoltransactions = models.CharField(
        max_length=255,
        blank=True,
    )

    stolencards = models.BooleanField(default=False)

    stolcards = models.CharField(
        max_length=255,
        blank=True,
    )

    stolentobacco = models.BooleanField(default=False)

    stoltobacco = models.CharField(
        max_length=255,
        blank=True,
    )

    stolenlottery = models.BooleanField(default=False)

    stollottery = models.CharField(
        max_length=255,
        blank=True,
    )

    stolenfuel = models.BooleanField(default=False)

    stolfuel = models.CharField(
        max_length=255,
        blank=True,
    )

    stolenother = models.BooleanField(default=False)

    stolother = models.CharField(
        max_length=255,
        blank=True,
    )

    stolenothervalue = models.CharField(
        max_length=255,
        blank=True,
    )

    stolenna = models.BooleanField(default=False)

    # -------------------------------------------------------------------------
    # Person description
    # -------------------------------------------------------------------------

    gender = models.CharField(max_length=255, blank=True)
    height = models.CharField(max_length=255, blank=True)
    weight = models.CharField(max_length=255, blank=True)
    haircolor = models.CharField(max_length=255, blank=True)
    haircut = models.CharField(max_length=255, blank=True)
    complexion = models.CharField(max_length=255, blank=True)
    beardmoustache = models.CharField(max_length=255, blank=True)
    eyeeyeglasses = models.CharField(max_length=255, blank=True)

    # -------------------------------------------------------------------------
    # Vehicle information
    # -------------------------------------------------------------------------

    licencenumber = models.CharField(max_length=255, blank=True)
    makemodel = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=255, blank=True)

    # -------------------------------------------------------------------------
    # Additional identifying information
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Images and tenant ownership
    # -------------------------------------------------------------------------

    image_folder = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    user_employer = models.ForeignKey(
        Employer,
        on_delete=models.SET_NULL,
        null=True,
    )

    # -------------------------------------------------------------------------
    # Section 2 - Investigation information
    #
    # These are optional because Section 1 may be completed immediately,
    # while the investigation may be completed later.
    # -------------------------------------------------------------------------

    causalfactors = models.TextField(blank=True)

    determincauses = models.TextField(blank=True)

    preventiveactions = models.TextField(blank=True)

    # -------------------------------------------------------------------------
    # Section 3 - Shared learning
    # -------------------------------------------------------------------------

    shared_learning_yes = models.BooleanField(default=False)
    shared_learning_no = models.BooleanField(default=False)
    shared_learning_na = models.BooleanField(default=False)

    shared_learning_date = models.DateField(
        blank=True,
        null=True,
    )

    shared_learning_method = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    # -------------------------------------------------------------------------
    # Emergency response plan actioned by
    # -------------------------------------------------------------------------

    emergency_not_applicable = models.BooleanField(default=False)
    emergency_no = models.BooleanField(default=False)
    emergency_site_staff = models.BooleanField(default=False)
    emergency_contractor = models.BooleanField(default=False)
    emergency_public = models.BooleanField(default=False)

    emergency_responders = models.BooleanField(
        default=False,
        help_text="Examples include 911, fire, police, or other responders.",
    )

    # -------------------------------------------------------------------------
    # Email tracking
    # -------------------------------------------------------------------------

    queued_for_sending = models.BooleanField(
        default=False,
        help_text="Indicates if this file is queued for sending.",
    )

    sent = models.BooleanField(default=False)

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The timestamp when the file was sent.",
    )

    do_not_send = models.BooleanField(default=False)

    def __str__(self):
        return f"Incident {self.pk}"

    def is_ready_to_send(self):
        """
        Determine whether the incident is ready to be sent.
        """
        return self.queued_for_sending and self.sent_at is None and not self.do_not_send


class MajorIncident(models.Model):
    brief_description = models.CharField(max_length=60, default="")
    robbery = models.BooleanField(default=False)
    breakandenter = models.BooleanField(default=False)
    assault = models.BooleanField(default=False)
    bombthreat = models.BooleanField(default=False)
    majorfireorexplosion = models.BooleanField(default=False)
    fatality = models.BooleanField(default=False)
    criticalinjury = models.BooleanField(default=False)

    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="majorincidents"
    )
    policeagency = models.CharField(max_length=60, default="", blank=True)
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
