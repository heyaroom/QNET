from qnet.algebra.hilbert_space_algebra import LocalSpace
from qnet.algebra.operator_algebra import LocalSigma, Destroy
from qnet.algebra.matrix_algebra import identity_matrix
from qnet.algebra.circuit_algebra import SLH
from qnet.algebra.state_algebra import BasisKet
from qnet.misc.qsd_codegen import QSDCodeGen, _cmd_list_to_str
from qnet.misc.testing_tools import datadir
from qnet.convert.to_qutip import SLH_to_qutip

import os

import numpy as np
import sympy
from sympy import symbols, sqrt, I
import qutip
import pytest

datadir = pytest.fixture(datadir)

def qutip_population(psi_of_t, state=0):
    return [float(abs(psi[state]))**2 for psi in psi_of_t]


def test_driven_tls(datadir):
    hs = LocalSpace('tls', basis=('g', 'e'))
    w =  symbols(r'\omega', real=True)
    pi = sympy.pi
    cos = sympy.cos
    t, T, E0 = symbols('t, T, E_0', real=True)
    a = 0.16
    blackman = 0.5 * (1 - a - cos(2*pi * t/T) + a*cos(4*pi*t/T))
    H0 =  Destroy(hs=hs).dag() * Destroy(hs=hs)
    H1 = LocalSigma('g', 'e', hs=hs) + LocalSigma('e', 'g', hs=hs)
    H = w*H0 + 0.5 * E0 * blackman * H1
    circuit = SLH(identity_matrix(0), [], H)
    num_vals = {w: 1.0, T:10.0, E0:1.0*2*np.pi}

    # test qutip conversion
    num_circuit = circuit.substitute(num_vals)
    H_qutip, Ls = SLH_to_qutip(num_circuit, time_symbol=t)
    assert len(Ls) == 0
    assert len(H_qutip) == 3
    times = np.linspace(0, num_vals[T], 201)
    psi0 = qutip.basis(2, 1)
    states = qutip.mesolve(H_qutip, psi0, times, [], []).states
    pop0 = np.array(qutip_population(states, state=0))
    pop1 = np.array(qutip_population(states, state=1))
    datfile = os.path.join(datadir, 'pops.dat')
    #print("DATFILE: %s" % datfile)
    #np.savetxt(datfile, np.c_[times, pop0, pop1, pop0+pop1])
    pop0_expect, pop1_expect = np.genfromtxt(datfile, unpack=True,
                                             usecols=(1,2))
    assert np.max(np.abs(pop0 - pop0_expect)) < 1e-12
    assert np.max(np.abs(pop1 - pop1_expect)) < 1e-12

    # Test QSD conversion
    codegen = QSDCodeGen(circuit, num_vals=num_vals, time_symbol=t)
    codegen.add_observable(LocalSigma('e', 'e', hs=hs), name='P_e')
    psi0 = BasisKet('e', hs=hs)
    codegen.set_trajectories(psi_initial=psi0,
            stepper='AdaptiveStep', dt=0.01,
            nt_plot_step=5, n_plot_steps=200, n_trajectories=1)
    scode = codegen.generate_code()
    compile_cmd = _cmd_list_to_str(codegen._build_compile_cmd(
                        qsd_lib='$HOME/local/lib/libqsd.a',
                        qsd_headers='$HOME/local/include/qsd/',
                        executable='test_driven_tls', path='$HOME/bin',
                        compiler='mpiCC', compile_options='-g -O0'))
    print(compile_cmd)
    codefile = os.path.join(datadir, "test_driven_tls.cc")
    #print("CODEFILE: %s" % codefile)
    #with(open(codefile, 'w')) as out_fh:
        #out_fh.write(scode)
        #out_fh.write("\n")
    with open(codefile) as in_fh:
        scode_expected = in_fh.read()
    assert scode.strip()  == scode_expected.strip()
    # When modifying this test, you should compile the codefile, run it, and
    # check that the resulting dynamics match those generated by qutip
