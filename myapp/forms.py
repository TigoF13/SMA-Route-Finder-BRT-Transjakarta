from django import forms

class RouteForm(forms.Form):
    halte_asal = forms.CharField(label="Halte Asal", max_length=100)
    halte_tujuan = forms.CharField(label="Halte Tujuan", max_length=100)
    preferensi = forms.ChoiceField(
        choices=[
            ("efisien", "Paling Efisien & Seimbang"),
            ("min_transit", "Minim Transit"),
            ("cepat", "Paling Cepat"),
        ],
        label="Preferensi Rute"
    )
    jam_berangkat = forms.TimeField(label="Jam Keberangkatan", input_formats=["%H:%M"])
    metode_solver = forms.ChoiceField(
        choices=[
            ("milp", "🧮 MILP (PuLP / CBC)"),
            ("sma", "🧠 Slime Mould Algorithm (SMA)"),
        ],
        label="Metode Solver",
        initial="milp"
    )
