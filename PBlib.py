#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Python library to handle Protein Blocks

2013 - P. Poulain, A. G. de Brevern
"""

## Use print as a function for python 3 compatibility
from __future__ import print_function

## standard modules
import os
import subprocess
import sys
import textwrap
import math

## third-party modules
import numpy
import matplotlib
import matplotlib.pyplot as plt

## Python2/Python3 compatibility
# The range function in python 3 behaves as the range function in python 2
# and returns a generator rather than a list. To produce a list in python 3,
# one should use list(range). Here we change range to behave the same in
# python 2 and in python 3. In both cases, range will return a generator.
try:
    range = xrange
except NameError:
    pass

## Data
# Protein Blocks reference angles
# taken from A. G. de Brevern, C. Etchebest and S. Hazout.
# "Bayesian probabilistic approach for predicting backbone structures
# in terms of protein blocks"
# Proteins, 41: 271-288 (2000)
REFERENCES = {
    'a': [ 41.14,   75.53,  13.92,  -99.80,  131.88,  -96.27, 122.08,  -99.68],
    'b': [108.24,  -90.12, 119.54,  -92.21,  -18.06, -128.93, 147.04,  -99.90],
    'c': [-11.61, -105.66,  94.81, -106.09,  133.56, -106.93, 135.97, -100.63],
    'd': [141.98, -112.79, 132.20, -114.79,  140.11, -111.05, 139.54, -103.16],
    'e': [133.25, -112.37, 137.64, -108.13,  133.00,  -87.30, 120.54,   77.40],
    'f': [116.40, -105.53, 129.32,  -96.68,  140.72,  -74.19, -26.65,  -94.51],
    'g': [  0.40,  -81.83,   4.91, -100.59,   85.50,  -71.65, 130.78,   84.98],
    'h': [119.14, -102.58, 130.83,  -67.91,  121.55,   76.25,  -2.95,  -90.88],
    'i': [130.68,  -56.92, 119.26,   77.85,   10.42,  -99.43, 141.40,  -98.01],
    'j': [114.32, -121.47, 118.14,   82.88, -150.05,  -83.81,  23.35,  -85.82],
    'k': [117.16,  -95.41, 140.40,  -59.35,  -29.23,  -72.39, -25.08,  -76.16],
    'l': [139.20,  -55.96, -32.70,  -68.51,  -26.09,  -74.44, -22.60,  -71.74],
    'm': [-39.62,  -64.73, -39.52,  -65.54,  -38.88,  -66.89, -37.76,  -70.19],
    'n': [-35.34,  -65.03, -38.12,  -66.34,  -29.51,  -89.10,  -2.91,   77.90],
    'o': [-45.29,  -67.44, -27.72,  -87.27,    5.13,   77.49,  30.71,  -93.23],
    'p': [-27.09,  -86.14,   0.30,   59.85,   21.51,  -96.30, 132.67,  -92.91],
}
#   PB  psi(n-2) phi(n-1) psi(n-1)   phi(n)  psi(n)  phi(n+1) psi(n+1) phi(n+2)

NAMES = 'abcdefghijklmnop'  # name of the 16 PBs
SUBSTITUTION_MATRIX_NAME = os.path.join(os.path.dirname(__file__),
                                        "PBs_substitution_matrix.dat")
FASTA_WIDTH = 60  # line width for fasta format


class SizeError(AssertionError):
    """
    Exception raised when a sequence does not have the expected length.
    """
    pass


class InvalidBlockError(ValueError):
    """
    Exception raised when encounter an invalid protein block.
    """
    def __init__(self, block=None):
        super(InvalidBlockError, self).__init__(self)
        self.block = block

    def __repr__(self):
        if self.block is None:
            return "Invald block"
        else:
            return "Ivalid block '{}'".format(self.block)


class RError(RuntimeError):
    """
    Exception raised when something fails with a R script.
    """
    pass


def read_fasta(name):
    """
    Read fasta file and output sequences in a list.

    Parameters
    ----------
    name : str
        Name of file containing sequences in fasta format.

    Returns
    -------
    header_lst : list
        List of headers (str)
    sequence_lst : list
        List of sequences (str)
    """
    assert os.path.exists(name), name + ' does not exist'
    sequence_lst = []
    header_lst = []
    header = ""
    sequence = ""
    with open(name, "rt") as f_in:
        for line in f_in:
            data = line.strip()
            # jump empty lines
            if not data:
                continue
            # store header and sequence when a new header
            # (i.e. sequence) is found
            if sequence and header and data.startswith(">"):
                header_lst.append(header)
                sequence_lst.append(sequence)
                # reset header and sequence
                header = ""
                sequence = ""
            # save header of sequence
            if data.startswith(">"):
                header = data[1:]
            # save sequence
            if ">" not in data:
                sequence += data
    # save last sequence
    if header and sequence:
        header_lst.append(header)
        sequence_lst.append(sequence)
    # outputs
    assert len(header_lst) == len(sequence_lst), \
        "cannot read same number of headers and sequences"
    print("read %d sequences in %s" % (len(sequence_lst), name))
    if len(sequence_lst) == 0:
        print("WARNING: {} seems empty of sequence".format(name))
    return header_lst, sequence_lst


def read_several_fasta(input_files):
    """
    Read several fasta files

    Note that each fasta file may contain several sequences.

    Parameters
    ----------
    input_files: a list of fasta file paths.

    Returns
    -------
    pb_name: a list of the headers
    pb_seq: a list of the sequences
    """
    pb_seq = []
    pb_name = []
    for name in input_files:
        header, seq = read_fasta(name)
        pb_name += header
        pb_seq += seq
    return pb_name, pb_seq


def assert_same_size(sequences):
    """
    Raise an exception is all sequence are not the same length.

    Parameters
    ----------
    sequences: a list of sequences

    Exceptions
    ----------
    SizeError : not all the sequences are the same length.
    """
    seq_size = len(sequences[0])
    for seq in sequences:
        if len(seq) != seq_size:
            raise SizeError


def load_substitution_matrix(name):
    """
    Load PB substitution matrix.

    The matrix must be 16x16.

    Parameters
    ----------
    name : str
        Name of the file containing the PBs susbtitution matrix.

    Returns
    -------
    mat : numpy array
        Array of floats.

    Exceptions
    ----------
    InvalidBlockError : encountered an unexpected PB
    """
    mat = numpy.loadtxt(name, dtype=float, skiprows=2)
    assert mat.shape == (16, 16), 'wrong substitution matrix size'
    for i in range(len(mat)):
        for j in range(len(mat[0])):
            if mat[i][j] != mat[j][i]:
                raise ValueError("Matrix is not symetric - idx {} and {}".format(i, j))
    return mat


def write_fasta_entry(outfile, sequence, comment, width=FASTA_WIDTH):
    """
    Write a fasta entry (header + sequence) in an open file

    Parameters
    ----------
    name : file descriptor
        The file descriptor to write in. It must allow writing.
    sequence : str
        Sequence to format.
    comment : str
        Comment to make header of sequence.
    width : int
        The width of a line. `FASTA_WIDTH` by default.
    """
    print('>' + comment, file=outfile)
    print(textwrap.fill(sequence, width=width), file=outfile)


def write_fasta(outfile, sequences, comments):
    for sequence, comment in zip(sequences, comments):
        write_fasta_entry(outfile, sequence, comment)


def write_flat(outfile, sequences):
    for sequence in sequences:
        print(sequence, file=outfile)


def count_to_transfac(identifier, count_content):
    """
    Convert a table of PB frequencies into transfac format

    http://meme.sdsc.edu/meme/doc/transfac-format.html

    Parameters
    ----------
    identifier : str
        Chain used for the ID property in the output.
    count_content :
        Content of the count file outputed by PBcount as a list of lines.

    Return
    ------
    The frequency matrix as a string in the transfac format.
    """
    residue_lst = []
    transfac_content = "ID %s\n" % identifier
    transfac_content += "BF unknown\n"
    transfac_content += "P0" + count_content[0][2:]
    for line in count_content[1:]:
        item = line.split()
        residue = int(item[0])
        residue_lst.append(residue)
        transfac_content += "%05d " % residue + line[5:-1] + "    X" + "\n"
    transfac_content += "XX\n"
    transfac_content += "//"
    return transfac_content


def assign(dihedrals, pb_ref=REFERENCES):
    """
    Assign Protein Blocks.

    Dihedral angles are provided as a dictionnary with one item per residue.
    The key is the residue number, and the value is a dictionnary with phi and
    psi as keys, and the dihedral angles as values.

    The protein block definitions are provided as a dictionnary. Each key is a
    block name, the values are lists of dihedral angles.

    Parameters
    ----------
    dihedrals : dict
        Phi and psi dihedral angles for each residue.
    pb_ref : dict
        The definition of the protein blocks.
    """
    pb_seq = ""
    # iterate over all residues
    for res in sorted(dihedrals):
        angles = []
        # try to get all eight angles required for PB assignement
        try:
            angles.append(dihedrals[res-2]["psi"])
            angles.append(dihedrals[res-1]["phi"])
            angles.append(dihedrals[res-1]["psi"])
            angles.append(dihedrals[res  ]["phi"])
            angles.append(dihedrals[res  ]["psi"])
            angles.append(dihedrals[res+1]["phi"])
            angles.append(dihedrals[res+1]["psi"])
            angles.append(dihedrals[res+2]["phi"])
            # check for bad angles
            # (error while calculating torsion: missing atoms)
            if None in angles:
                pb_seq += "Z"
                continue

        # cannot get required angles (Nter, Cter or missign residues)
        # -> cannot assign PB
        # jump to next residue
        except KeyError:
            pb_seq += "Z"
            continue

        # convert to array
        angles = numpy.array(angles)

        # compare to reference PB angles
        rmsda_lst = {}
        for block in pb_ref:
            diff = pb_ref[block] - angles
            diff2 = angle_modulo_360_vect(diff)
            rmsda = numpy.sum(diff2**2)
            rmsda_lst[rmsda] = block
        pb_seq += rmsda_lst[min(rmsda_lst)]
    return pb_seq


def angle_modulo_360(angle):
    """
    Keep angle in the range -180 / +180 [degrees]
    """
    if angle > 180.0:
        return angle - 360.0
    elif angle < -180.0:
        return angle + 360.0
    else:
        return angle


def write_phipsi_entry(outfile, torsion, comment):
    for res in sorted(torsion):
        try:
            phi = "%8.2f" % torsion[res]["phi"]
        except TypeError:
            phi = "    None"
        try:
            psi = "%8.2f" % torsion[res]["psi"]
        except TypeError:
            psi = "    None"
        print("{} {:6d} {} {} ".format(comment, res, phi, psi), file=outfile)


def write_phipsi(outfile, torsions, comments):
    for torsion, comment in zip(torsions, comments):
        write_phipsi_entry(outfile, torsion, comment)


def count_matrix(pb_seq):
    """
    Count the occurences of each block at each position.

    The occurence matrix has one row per sequence, and one column per block.
    The columns are ordered in as PB.NAMES.

    Parameters
    ----------
    pb_seq: a list of PB sequences.

    Returns
    -------
    The occurence matrix.

    Exceptions
    ----------
    InvalidBlockError : encountered an unexpected PB
    """
    assert_same_size(pb_seq)
    pb_count = numpy.zeros((len(pb_seq[0]),  len(NAMES)))
    for seq in pb_seq:
        for idx, block in enumerate(seq):
            if block in NAMES:
                pb_count[idx, NAMES.index(block)] += 1.0
            elif block not in ["Z", "z"]:
                raise InvalidBlockError(block=block)
    return pb_count


def write_count_matrix(pb_count, outfile, first=1):
    """
    Write a PB occurence matrix in a file.

    Parameters
    ----------
    pb_count: an occurence matrix as a 2D numpy array.
    outfile: an open file where to write the matrix.
    first: the residue number of the first position.
    """
    # write the header (PB names)
    print("    " + "".join(["%6s" % name for name in NAMES]), file=outfile)
    # write the data table
    for residue_idx, residue_pb in enumerate(pb_count):
        print("%-5d" % (residue_idx + first) +
              " ".join("%5d" % i for i in residue_pb), file=outfile)


def compute_score_by_position(score_mat, seq1, seq2):
    """
    Computes substitution score between two sequences position per position

    The substitution score can represent a similarity or a distance depending
    on the score matrix provided. The score matrix should be provided as a 2D
    numpy array with score[i, j] the score to swich the PB at the i-th position
    in PB.NAMES to the PB at the j-th position in PB.NAMES.

    The function returns the result as a list of substitution scores to go from
    `seq1` to `seq2` for each position. Both sequences must have the same
    length.

    ..note:

        The score to move from or to a Z block (dummy block) is always 0.

    Exceptions
    ----------
    InvalidBlockError : encountered an unexpected PB
    """
    assert len(seq1) == len(seq2), \
        "sequences have different sizes:\n{}\nvs\n{}".format(seq1, seq2)
    score = []
    for pb1, pb2 in zip(seq1, seq2):
        # score is 0 for Z (dummy PB)
        if "z" in [pb1.lower(), pb2.lower()]:
            score.append(0)
        elif pb1 in NAMES and pb2 in NAMES:
            score.append(score_mat[NAMES.index(pb1)][NAMES.index(pb2)])
        else:
            invalid = []
            for pb in (pb1, pb2):
                if not pb in NAMES:
                    invalid.append(pb)
            raise InvalidBlockError(', '.join(invalid))
    return score


def matrix_to_single_digit(matrix):
    """
    Convert a similarity substitution matrix to a single digit distance
    substitution matrix

    This function takes a substitution matrix expressed as similarity scores,
    and expresses it as integer distances in the range [0; 9]. Where 0 means
    similar PBs, and 9 means different PBs.

    Such single digit substitution matrix is convenient to display sequences
    of substitution scores.

    ..note:

        If a substitution matrix expressed with distances is provided
        rather than a matrix expressed with similarity scores, then the
        returned matrix is expressed with similarity scores.
    """
    mini = numpy.min(matrix)
    maxi = numpy.max(matrix)
    # Normalize between 0 and 1
    mat_modified = (matrix - mini)/(maxi - mini)
    # Convert similarity scores to distances and change the range to [0; 9]
    mat_modified = 9 * (1 - mat_modified)
    # Convert to integers
    mat_modified = mat_modified.astype(int)
    # Set diagonal to 0
    numpy.fill_diagonal(mat_modified, 0)
    return mat_modified


def distance_matrix(sequences, substitution_mat):
    """
    Compute distances of all sequences against all the others

    The substitution matrix is expected to be expressed as similarity scores.
    """
    distance_mat = numpy.empty((len(sequences), len(sequences)), dtype='float')

    print("Building distance matrix")
    # Get similarity score
    for i, seqA in enumerate(sequences):
        sys.stdout.write("\r%.f%%" % (float(i+1)/len(sequences)*100))
        sys.stdout.flush()
        for j, seqB in enumerate(sequences[i:], start=i):
            score = substitution_score(substitution_mat, seqA, seqB)
            distance_mat[i, j] = score
            distance_mat[j, i] = score
    print("")
    # Set the diagonal equal to its maximum value
    diag_maxi = numpy.max(distance_mat.diagonal())
    numpy.fill_diagonal(distance_mat, diag_maxi)
    # Convert similarity score into a distance
    mini = numpy.min(distance_mat)
    maxi = numpy.max(distance_mat)
    # Compute distance
    distance_mat = 1 - (distance_mat - mini)/(maxi - mini)
    # Check distance values are in expected range
    assert(numpy.min(distance_mat) >= 0.0)
    assert(numpy.max(distance_mat) <= 1.0)
    assert(numpy.sum(distance_mat.diagonal()) == 0.0)
    return distance_mat


def substitution_score(substitution_matrix, seqA, seqB):
    """
    Compute the substitution score to go from `seqA` to `seqB`

    Both sequences must have the same length.

    The score is either expressed as a similarity or a distance depending on
    the substitution matrix.
    """
    return sum(compute_score_by_position(substitution_matrix, seqA, seqB))


def _matrix_to_str(distance_mat):
    numpy.set_printoptions(threshold=numpy.inf, precision=3, linewidth=100000)
    output_mat_str = numpy.array_str(distance_mat).replace('[', '').replace(']', '')
    return output_mat_str


def hclust(distance_mat, nclusters, method='ward'):
    """
    Hierachical clustering using R

    Parameters
    ----------
    distance_mat : 2D numpy array
        Distance matrix
    nclusters : int
        Number of cluster to build
    method : str
        Aggregation method for the clustering algorithm; must be a value
        valid for R hclust function

    Returns
    -------
    cluster_id : list of int
        Cluster ID for each item; starts at 1
    medoid_id : list of int
        Index of the medoid for each cluster

    Exceptions
    ----------
    RError : something wrong happened with R
    """
    # Convert the distance matrix into a string readable by R
    output_mat_str = _matrix_to_str(distance_mat)
    # Build the R script
    R_script = """
    connector = textConnection("{matrix}")
    distances = read.table(connector, header=FALSE)
    rownames(distances) = colnames(distances)

    clusters = cutree(hclust(as.dist(distances), method="{method}"), k={clusters})
    distances = as.matrix(distances)

    # function to find medoid in cluster i
    # http://www.biostars.org/p/11987/
    clust.medoid = function(i, distmat, clusters) {{
        ind = (clusters == i)

        if(length(distmat[ind, ind]) == 1){{
            names(clusters[ind])
        }} else {{
            names(which.min(rowSums( distmat[ind, ind] )))
            # c(min(rowMeans( distmat[ind, ind] )))
        }}
    }}

    medoids = sapply(unique(clusters), clust.medoid, distances, clusters)

    cat("cluster_id", clusters, "\n")
    cat("medoid_id", medoids)
    """.format(matrix=output_mat_str, clusters=nclusters, method=method)

    # Execute the R script
    command = "R --vanilla --slave"
    proc = subprocess.Popen(command, shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE)
    (out, err) = proc.communicate(R_script.encode('utf-8'))
    out = out.decode('utf-8')
    err = err.decode('utf-8')
    if err:
        raise RError("{0}".format(err))
    code = proc.wait()
    if code:
        raise RError("R returned with code {}".format(code))

    # Extract the output of the R script
    # only 2 lines are expected
    if len(out.split("\n")) != 2:
        raise RError("unexpected R ouput")
    cluster_id, medoid_id = out.split("\n")
    # As the input table is provided without headers, the sequences are named
    # V1, V2... with indices starting at 1. To get a integer index starting at
    # 0 from a sequence name, we need to remove the V prefix and to substract 1
    # from the remaining number. This applies to medoid_id that relies on the
    # sequence name, but not to cluster_id that is already a list of integers.
    cluster_id = [int(x) for x in cluster_id.split()[1:]]
    medoid_id = [int(x[1:]) - 1 for x in medoid_id.split()[1:]]

    return cluster_id, medoid_id


def compare_to_first_sequence(headers, sequences, substitution_mat):
    """
    Compare all sequence to the first one
    """
    iheaders = iter(headers)
    isequences = iter(sequences)
    ref_name = next(iheaders)
    ref_seq = next(isequences)
    for target_header, target_seq in zip(iheaders, isequences):
        header = "%s vs %s" % (ref_name, target_header)
        score_lst = compute_score_by_position(substitution_mat, ref_seq, target_seq)
        yield header, score_lst


def _slice_matrix(mat, residue_min=1, residue_max=None):
    """
    Slice a matrix given the lower and upper bond in parameters.
    The matrix has to be a numpy array with one row per residue.
    The slice will occurs on the rows and the sub-matrix is returned.

    Parameters
    ----------
    mat : numpy array
        the matrix to slice
    residue_min: int
        the lower bound of residue frame
    residue_max: int
        the upper bound of residue frame

    Returns
    -------
    sub_mat: numpy 2D array
        the matrix sliced

    Exceptions
    ----------
    IndexError : when something is wrong about the lower/upper bound
    """

    if residue_max is None:
        residue_max = mat.shape[0]

    if residue_min <= 0 or residue_max <= 0:
        raise IndexError("Index start at 1")

    # range of indexes of the matrix
    residues_idx = range(1, mat.shape[0] + 1)

    if residue_min not in residues_idx or residue_max not in residues_idx:
        raise IndexError("Index out of range")

    if residue_min >= residue_max:
        raise IndexError("Lower bound > upper bound")

    return mat[residue_min - 1: residue_max]


def compute_freq_matrix(count_mat):
    """
    Compute a PB frequency matrix from an occurence matrix.

    The frequency matrix has one row per sequence, and one column per block.
    The columns are ordered in as PB.NAMES.

    Parameters
    ----------
    count_mat : numpy array
        an occurence matrix returned by `count_matrix`.

    Returns
    -------
    freq : numpy array
        The frequency matrix
    """

    # Assert the occurence matrix is in the good format
    nb_pb = count_mat.shape[1]
    if nb_pb != len(NAMES):
        raise ValueError("Wrong number of PB({} should be {}".format(nb_pb, len(NAMES)))

    # Retrieve the number of sequences compiled
    # use the sum of all residue at position 3 since positions 1 and 2 have no PBs assignement
    nb_sequences = sum(count_mat[2, :])

    return count_mat / float(nb_sequences)


def _neq_per_residue(row_freq):
    """
    Compute the Neq of a vector of frequencies coresponding to one residue.
    The vector is a row of the frequency matrix.
    This function is intended to be called from the `numpy.apply_along_axis` function.

    Parameters
    ----------
    row_freq : 1D numpy array
        vector of frequencies

    Return
    ------
        The value of the Neq
    """

    H = sum([math.log(freq)*freq for freq in row_freq if freq != 0])

    return math.exp(-H)


def compute_neq(count_mat):
    """
    Compute the Neq for each residue from an occurence matrix.

    Parameters
    ----------
    count_mat : numpy array
        an occurence matrix returned by `count_matrix`.

    Returns
    -------
    neq_array : numpy array
        a 1D array containing the neq values
    """

    # get the frequency matrix
    freq = compute_freq_matrix(count_mat)

    # Compute neq
    neq_array = numpy.apply_along_axis(_neq_per_residue, 1, freq)

    return neq_array


def write_neq(outfile, neq_array, residue_min=1, residue_max=None):
    """
    Write the Neq matrix in an open file

    Parameters
    ----------
    outfile : file descriptor
        The file descriptor to write in. It must allow writing.
    neq_array : numpy array
        a 1D array containing the neq values.
    residue_min: int
        the lower bound of residue frame
    residue_max: int
        the upper bound of residue frame

    """

    # Slice
    neq = _slice_matrix(neq_array, residue_min, residue_max)

    print("%-6s %8s " % ("resid", "Neq"), file=outfile)
    for (res, neq) in enumerate(neq):
        print("%-6d %8.2f " % (res + residue_min, neq), file=outfile)


def plot_neq(fname, neq_array, residue_min=1, residue_max=None):
    """
    Generate the Neq plot along the protein sequence

    Parameters
    ----------
    neq_array : numpy array
        an array containing the neq value associated to the residue number
    fname : str
        The path to the file to write in
    residue_min: int
        the lower bound of the protein sequence
    residue_max: int
        the upper bound of the protein sequence
    """

    neq = _slice_matrix(neq_array, residue_min, residue_max)
    nb_residues = neq.shape[0]

    # Residue number with good offset given the slice
    x = numpy.arange(residue_min, residue_min + nb_residues)

    fig = plt.figure(figsize=(2.0*math.log(nb_residues), 5))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_ylim([0, round(max(neq), 0)+1])
    ax.plot(x, neq)
    ax.set_xlabel('Residue number', fontsize=18)
    ax.set_ylabel('Neq', fontsize=18, style='italic')
    fig.savefig(fname)


def plot_map(fname, count_mat, residue_min=1, residue_max=None):
    """
    Generate a map of the distribution of PBs along protein sequence from
    an occurence matrix.

    Parameters
    ----------
    fname : str
        The path to the file to write in
    count_mat : numpy array
        an occurence matrix returned by `count_matrix`.
    residue_min: int
        the lower bound of the protein sequence
    residue_max: int
        the upper bound of the protein sequence
    """

    # Get the frequency matrix
    freq_mat = compute_freq_matrix(count_mat)
    # Slice it
    freq = _slice_matrix(freq_mat, residue_min, residue_max)
    nb_residues = freq.shape[0]
    # Residue number with good offset given the slice
    x = numpy.arange(residue_min, residue_min + nb_residues)

    # define ticks for x-axis
    x_step = 5
    xticks = x[::x_step]
    # trying to round ticks: 5, 10, 15 instead of 6, 11, 16...
    if xticks[0] == 1:
        xticks = xticks-1
        xticks[0] += 1

    yticks = ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h',
              'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p')

    fig = plt.figure(figsize=(2.0*math.log(nb_residues), 4))
    ax = fig.add_axes([0.1, 0.1, 0.75, 0.8])

    # Color scheme inspired from ColorBrewer
    # http://colorbrewer2.org/?type=diverging&scheme=RdYlBu&n=5
    # This color scheme is colorblind safe
    colors = [(44.0 / 255, 123.0 / 255, 182.0 / 255),
              (171.0 / 255, 217.0 / 255, 233.0 / 255),
              (255.0 / 255, 255.0 / 255, 191.0 / 255),
              (253.0 / 255, 174.0 / 255, 97.0 / 255),
              (215.0 / 255, 25.0 / 255, 28.0 / 255)]
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list('ColBrewerRdYlBu', colors)

    img = ax.imshow(numpy.transpose(freq[:, :]), interpolation='none', vmin=0, vmax=1,
                    origin='lower', aspect='auto', cmap=cmap)

    ax.set_xticks(xticks - numpy.min(xticks))
    ax.set_xticklabels(xticks)
    ax.set_yticks(range(len(yticks)))
    ax.set_yticklabels(yticks, style='italic', weight='bold')
    colorbar_ax = fig.add_axes([0.87, 0.1, 0.03, 0.8])
    fig.colorbar(img, cax=colorbar_ax)
    # print "beta-strand", "coil" and "alpha-helix" text
    # only if there is more than 20 residues
    if nb_residues >= 20:
        # center alpha-helix: PB m (13th PB out of 16 PBs)
        # center coil: PB h and i (8th and 9th PBs out of 16 PBs)
        # center beta-sheet: PB d (4th PB out of 16 PBs)
        fig.text(0.05, 4.0/16*0.8+0.075, r"$\beta$-strand", rotation=90,
                 va='center', transform=ax.transAxes)
        fig.text(0.05, 8.5/16*0.8+0.075, r"coil", rotation=90,
                 va='center')
        fig.text(0.05, 13.0/16*0.8+0.075, r"$\alpha$-helix", rotation=90,
                 va='center', transform=ax.transAxes)

    fig.text(0.01, 0.5, "PBs", rotation=90, weight="bold",
             size='larger', transform=ax.transAxes)
    fig.text(0.4, 0.01, "Residue number", weight="bold")
    fig.text(0.96, 0.6, "Intensity", rotation=90, weight="bold")
    fig.savefig(fname, dpi=300)


# vertorize function
angle_modulo_360_vect = numpy.vectorize(angle_modulo_360)
angle_modulo_360_vect.__doc__ = angle_modulo_360.__doc__
