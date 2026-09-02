"""Simulation models, and exactly what each one is allowed to establish.

One model is registered here: the flyback diode's forward characteristic,
derived from the frozen datasheet rather than taken from a vendor library.

The derivation is worth stating, because it is what makes the model an upper
bound rather than a guess. The datasheet gives maximum forward voltage at four
currents. Any diode of the standard form

    V(I) = N.Vt.ln(I / IS) + I.RS,    RS >= 0

is convex in ln(I) - the first term is linear in ln(I), the second is a
positive exponential of it - and a convex function lies below its own chord.
The chord drawn between two datasheet maxima therefore lies at or above every
such device that meets those two limits, so a two-parameter fit through a pair
of maxima with RS = 0, which IS that chord, bounds the real part's forward
voltage from above between them.

That bound is only claimed between the two points it was fitted through. Below
the lower one and above the upper one the same expression is an extrapolation
and this module refuses to let a scenario rely on it there.

Nothing here is measured from the board, so no model registered here carries a
board digest; the extracted copper model, which does, is built during
validation from the board itself.
"""
from __future__ import annotations

import json
import math
import os
import sys

from . import netlist, rules

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_PATH = os.path.join(REPO_ROOT, "sim", "models.json")

FLYBACK_DIODE = "flyback_diode_1n4148w"

#: The two datasheet currents the chord is drawn between, in amperes. They
#: bracket the coil current this board's flyback device actually carries, and
#: that containment is checked rather than assumed.
FIT_CURRENTS_A = (0.05, 0.15)

#: Boltzmann's constant over the elementary charge, in volts per kelvin.
K_OVER_Q = 8.617333262e-5

ABSOLUTE_ZERO_C = -273.15


def thermal_voltage(temperature_c):
    return K_OVER_Q * (temperature_c - ABSOLUTE_ZERO_C)


def _diode_spec(parameters):
    return rules._spec(parameters, "D1")["diode"]


def fit(parameters):
    """The chord through two datasheet maxima, as (n_vt, saturation_current).

    Returned as the product N.Vt rather than N alone: the fit determines the
    product, and splitting it needs the temperature the datasheet states its
    characteristics at, which is carried separately as the model's condition.
    """
    spec = _diode_spec(parameters)
    points = spec["forward_voltage_max_v"]
    low, high = FIT_CURRENTS_A
    try:
        v_low = points["%g" % low]["value"]
        v_high = points["%g" % high]["value"]
    except KeyError:
        raise KeyError(
            "the datasheet points the diode model is fitted through (%g A and "
            "%g A) are not both frozen in components/parameters.json"
            % (low, high))
    n_vt = (v_high - v_low) / math.log(high / low)
    saturation_a = low * math.exp(-v_low / n_vt)
    return n_vt, saturation_a


def forward_voltage(parameters, current_a):
    """The bound this model places on forward voltage at one current."""
    low, high = FIT_CURRENTS_A
    if not low <= current_a <= high:
        raise ValueError(
            "%g A is outside the %g..%g A range the diode model is fitted "
            "over; the expression is an extrapolation there and this model "
            "does not bound it" % (current_a, low, high))
    n_vt, saturation_a = fit(parameters)
    return n_vt * math.log(current_a / saturation_a)


def spice_text(parameters):
    spec = _diode_spec(parameters)
    temperature_c = spec["characteristics_temperature_c"]["value"]
    n_vt, saturation_a = fit(parameters)
    emission = n_vt / thermal_voltage(temperature_c)
    return "\n".join((
        ".subckt %s a k" % FLYBACK_DIODE,
        "D1 a k %s_junction" % FLYBACK_DIODE,
        ".model %s_junction D(IS=%.6e N=%.6f RS=0 TNOM=%g)"
        % (FLYBACK_DIODE, saturation_a, emission, temperature_c),
        ".ends %s" % FLYBACK_DIODE,
    ))


def flyback_diode(parameters):
    spec = _diode_spec(parameters)
    temperature_c = spec["characteristics_temperature_c"]["value"]
    n_vt, saturation_a = fit(parameters)
    low, high = FIT_CURRENTS_A
    points = spec["forward_voltage_max_v"]
    return {
        "identity": FLYBACK_DIODE,
        "kind": "diode",
        "ports": ["a", "k"],
        "spice": spice_text(parameters),
        "evidence": [{
            "phenomenon": "device_electrical",
            "evidence_class": "datasheet-behavioral",
            "provenance": {"source": "components/parameters.json",
                           "documents": ["1n4148w_semtech"]},
            "applicability": {
                "status": "applicable",
                "detail": "forward conduction between %g A and %g A, where "
                          "the fitted expression is a chord between two "
                          "datasheet maxima and bounds the real device's "
                          "forward voltage from above" % (low, high)},
            "assumptions": [
                "the real device obeys V = N.Vt.ln(I/IS) + I.RS with a "
                "non-negative series resistance, which is what makes its "
                "curve convex in ln(I) and so no higher than the chord",
                "the datasheet's stated maxima are limits the part is not "
                "allowed to exceed, so a device passing at or below both "
                "endpoints lies at or below this chord throughout",
            ],
            "omitted_contributions": [
                "reverse recovery, which the datasheet states as a time "
                "rather than a charge and which this model does not "
                "represent",
                "self-heating: the fit is at the single ambient the "
                "datasheet characterises and the model does not respond to "
                "junction temperature",
                "junction capacitance, which is stated but not fitted "
                "because no scenario here asks a question it would change",
            ],
        }],
        "conditions": {
            "temperature_c": {
                "kind": "fixed-reference",
                "value": temperature_c,
                "units": "degC",
                "source": "the ambient the datasheet states its forward "
                          "characteristics at",
            },
        },
        "derivation": {
            "method": "two-point chord through datasheet forward-voltage "
                      "maxima, fitted with zero series resistance",
            "fitted_through": [{"current_a": low, "max_forward_v":
                                points["%g" % low]["value"]},
                               {"current_a": high, "max_forward_v":
                                points["%g" % high]["value"]}],
            "n_times_thermal_voltage_v": round(n_vt, 9),
            "saturation_current_a": saturation_a,
            "valid_current_range_a": [low, high],
            "bound_direction": "upper_bound",
            "bound_argument": "V(I) = N.Vt.ln(I/IS) + I.RS is convex in ln(I) "
                              "for RS >= 0, so it lies at or below its chord; "
                              "the chord is drawn through the datasheet's "
                              "maxima, which the real device may not exceed",
            "other_datasheet_points_not_fitted": [
                {"current_a": float(current), "max_forward_v": record["value"]}
                for current, record in sorted(points.items(),
                                              key=lambda item: float(item[0]))
                if float(current) not in FIT_CURRENTS_A],
        },
        "notes": "not a vendor model and not a device model: an upper-bound "
                 "envelope of one datasheet limit over one current range. "
                 "The emission coefficient it carries is a fit artefact and "
                 "is not a physical property of the part.",
    }


def records(parameters=None):
    parameters = parameters or rules.load_parameters()
    return [flyback_diode(parameters)]


def check(parameters=None):
    """The model's validity range actually covers the current it is used at."""
    parameters = parameters or rules.load_parameters()
    supply = rules.Supply(parameters)
    low, high = FIT_CURRENTS_A
    current = supply.coil_current_max_a
    if not low <= current <= high:
        raise ValueError(
            "the flyback diode carries %.4g A, which is outside the %g..%g A "
            "range its model is fitted over" % (current, low, high))
    for record in records(parameters):
        sys.path.insert(0, rules.TOOLKIT_ROOT)
        from pcbqa.sim import model_registry
        model_registry.validate_model(record)
    return True


def write():
    parameters = rules.load_parameters()
    check(parameters)
    os.makedirs(os.path.dirname(MODELS_PATH), exist_ok=True)
    with open(MODELS_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(records(parameters), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return MODELS_PATH


if __name__ == "__main__":
    parameters = rules.load_parameters()
    n_vt, saturation = fit(parameters)
    supply = rules.Supply(parameters)
    sys.stdout.write("N.Vt = %.6f V, IS = %.6e A\n" % (n_vt, saturation))
    for current in (0.05, supply.coil_current_max_a, 0.15):
        sys.stdout.write("  %7.4f A -> %.4f V\n"
                         % (current, forward_voltage(parameters, current)))
    sys.stdout.write(write() + "\n")
