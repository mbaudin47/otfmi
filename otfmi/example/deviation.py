#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2016 EDF. This software was developed with the collaboration of
# Phimeca Engineering (Sylvain Girard, girard@phimeca.com).
"""Estimate a threshold exeedance probability with both Python and FMU models.
The physical model represents the deviation of a cantilever beam subjected to
a load. The probability that the deviation exceeds a given threshold is
estimated by straightforward Monte Carlo sampling.
"""

#§ Identifying the platform
import platform
key_platform = (platform.system(), platform.architecture()[0])
# Call to either 'platform.system' or 'platform.architecture' *after*
# importing pyfmi causes a segfault.
dict_platform = {("Linux", "64bit"):"linux64",
                 ("Windows", "32bit"):"win32"}

#§ Define the input distribution
import numpy as np
import openturns as ot

from openturns import (Event, MonteCarlo,
                       Beta, LogNormal, Uniform, Greater, )


E = Beta(0.93, 3.2, 28000000.0, 48000000.0)
F = LogNormal(30000.0, 9000.0, 15000.0,  LogNormal.MUSIGMA)
L = Uniform(250.0, 260.0)
I = Beta(2.5, 4.0, 310.0, 450.0)


#§ Python model (reference)
def deviationFunction(x):
    """Python version of the physical model.

    Parameters:
    ----------
    x : Vector or array with individuals as rows, input values in the
    following order :
      - beam Young's modulus (E)
      - load (F)
      - length (L)
      - section modulus (I)

    """

    E=x[0]
    F=x[1]
    L=x[2]
    I=x[3]
    y=(F*L*L*L)/(3.*E*I)
    return [y]

deviation_py = ot.PythonFunction(4, 1, deviationFunction)
deviation_py.enableHistory()

#§ FMU model
import otfmi
from pyfmi.fmi import FMUException
import sys

import os


path_here = os.path.dirname(os.path.abspath(__file__))
try:
    directory_platform = dict_platform[key_platform]
    path_fmu = os.path.join(path_here, "file", "fmu",
                            directory_platform, "deviation.fmu")
    deviation_fmu = otfmi.FMUFunction(
        path_fmu, inputs_fmu=["E", "F", "L", "I"], outputs_fmu="y")
except (KeyError, FMUException):
    print ("This example is not available on your platform.\n"
           "Execution aborted.")
    sys.exit()

deviation_fmu.enableHistory()

def create_monte_carlo(model, inputRandomVector):
    """Create a Monte Carlo algorithm.

    Parameters:
    ----------
    model : OpenTURNS NumericalMathFunction.

    inputRandomVector : OpenTURNS RandomVector, vector of random inputs.

    """

    outputVariableOfInterest = ot.RandomVector(model, inputRandomVector)
    # Create an Event from this RandomVector
    threshold = 30
    myEvent = Event(outputVariableOfInterest, Greater(), threshold)
    myEvent.setName("Deviation > 30 cm")

    # Create a Monte Carlo algorithm
    myAlgoMonteCarlo = MonteCarlo(myEvent)
    myAlgoMonteCarlo.setBlockSize(100)
    myAlgoMonteCarlo.setMaximumCoefficientOfVariation(0.10)

    return myAlgoMonteCarlo

def run_monte_carlo(model):
    """Run Monte Carlo simulations.

    Parameters:
    ----------
    model : OpenTURNS NumericalMathFunction.

    """

    # Create the Spearman correlation matrix of the input random vector
    RS = ot.CorrelationMatrix(4)
    RS[2,3] = -0.2

    # Evaluate the correlation matrix of the Normal copula from RS
    R = ot.NormalCopula.GetCorrelationFromSpearmanCorrelation(RS)

    # Create the Normal copula parametrized by R
    mycopula = ot.NormalCopula(R)

    # Create the input probability distribution of dimension 4
    inputDistribution = ot.ComposedDistribution([E, F, L, I], mycopula)

    # Give a description of each component of the input distribution
    inputDistribution.setDescription( ("E", "F", "L", "I") )

    # Create the input random vector
    inputRandomVector = ot.RandomVector(inputDistribution)

    # Setup Monte Carlo algorithm
    myAlgoMonteCarlo = create_monte_carlo(model, inputRandomVector)

    # Perform the simulations
    myAlgoMonteCarlo.run()

    # Get the results
    monte_carlo_result = myAlgoMonteCarlo.getResult()
    probability = monte_carlo_result.getProbabilityEstimate()

    return probability

def run_demo(seed=23091926):
    """Run the demonstration

    Parameters:
    ----------
    seed : Integer, seed of the random number generator. The default is
    23091926.

    """
    import time

    ot.RandomGenerator.SetSeed(seed)
    time_start = time.time()
    probability_py = run_monte_carlo(deviation_py)
    elapsed_py = time.time() - time_start

    ot.RandomGenerator.SetSeed(seed)
    time_start = time.time()
    probability_fmu = run_monte_carlo(deviation_fmu)
    elapsed_fmu = time.time() - time_start

    title = "Threshold exeedance probability:"
    print "\n%s" % title
    print "-" * len(title)
    justify = 20
    print "Full python: %f".rjust(justify) % probability_py
    print "FMU: %f".rjust(justify) % probability_fmu

    relative_error = (abs(probability_py - probability_fmu) /
                      (probability_py + probability_fmu) / 2.)

    from numpy import finfo
    if relative_error < finfo(float).eps:
        print "Relative error is below machine precision"
    else:
        print "Relative error: %e" % relative_error

    title = "Computation time in seconds:"
    print "\n%s" % title
    print "-" * len(title)
    justify = 20
    print "Full python: %f".rjust(justify) % elapsed_py
    print "FMU: %f".rjust(justify) % elapsed_fmu

if __name__ == "__main__":
    run_demo()

#§
# Local Variables:
# tmux-temp-file: "/cluster/home/girard/.tmp/tmux_buffer"
# tmux-repl-window: "fmot"
# End:
