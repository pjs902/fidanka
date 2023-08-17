import numpy as np
import numpy.typing as npt
from typing import Callable, Tuple, Union
from numbers import Number
from scipy.interpolate import interp1d
import logging
from tqdm import tqdm
from collections.abc import Sequence

from fidanka.misc.logging import LoggerManager

from scipy.optimize import minimize
import matplotlib.pyplot as plt

FARRAY_1D = npt.NDArray


def inverse_cdf_sample(
    f: Callable[[FARRAY_1D], FARRAY_1D], x: FARRAY_1D = None
) -> Callable[[FARRAY_1D], FARRAY_1D]:
    """
    Generate a function that samples from the inverse CDF of a given function.

    Parameters
    ----------
        f : Callable[[FARRAY_1D], FARRAY_1D]
            Function to sample from.
        x : FARRAY_1D, default=None
            Domain of the function. If None, defaults to np.linspace(0,1,100000).

    Returns
    -------
        inverse_cdf : Callable[[FARRAY_1D], FARRAY_1D]
            Function that samples from the inverse CDF of f. To evaluate the
            function, pass an array of uniform random numbers between 0 and 1.

    Examples
    --------
    Let's sample from the inverse CDF of a Gaussian distribution. First, we
    define the Gaussian distribution.

    >>> def gaussian(x, mu=0, sigma=1):
    ...     return np.exp(-(x-mu)**2/(2*sigma**2))

    Then, we generate the inverse CDF function.

    >>> inverse_cdf = inverse_cdf_sample(gaussian)

    Finally, we sample from the inverse CDF.

    >>> inverse_cdf(np.random.random(10))
    """
    if x is None:
        x = np.linspace(0, 1, 100000)

    y = f(x)
    cdf_y = np.cumsum(y)
    cdf_y_norm = cdf_y / cdf_y.max()

    inverse_cdf = interp1d(cdf_y_norm, x, bounds_error=False, fill_value="extrapolate")

    return inverse_cdf


def get_samples(
    n: int, f: Callable[[FARRAY_1D], FARRAY_1D], domain: FARRAY_1D = None
) -> FARRAY_1D:
    """
    Sample n values from a given function. The function does not have to be
    a normalized PDF as the function will be normalized before sampling.

    Parameters
    ----------
        n : int
            Number of samples to draw.
        f : Callable[[FARRAY_1D], FARRAY_1D]
            Function to sample from.
        domain : FARRAY_1D, default=None
            Domain of the function. If None, defaults to np.linspace(0,1,100000).

    Returns
    -------
        samples : NDArray[float]
            Array of samples.

    Examples
    --------
    Let's sample 10 values from a quadratic function over the domain 0,2.

    >>> def quadratic(x):
    ...     return x**2

    >>> get_samples(10, quadratic, domain=np.linspace(0,2,1000))
    """

    uniformSamples = np.random.random(n)
    shiftedSamples = inverse_cdf_sample(f, x=domain)(uniformSamples)
    return shiftedSamples


def closest(
    array: Sequence[Number], target: Number
) -> Tuple[Union[float, None], Union[float, None]]:
    """
    Find the closest values above and below a given target in an array.
    If the target is in the array, the function returns the exact target value
    in both elements of the tuple. If the target is not exactly in the array,
    the function returns the closest value below the target in the first
    element of the tuple and the closest value above the target in the second
    element of the tuple. If the taret is below the minimum value in the array,
    the first element of the tuple is None. If the target is above the maximum
    value in the array, the second element of the tuple is None.

    Parameters
    ----------
        array : NDArray[float]
            Array to search.
        target : float
            Target value.

    Returns
    -------
        closest_lower : Union[NDArray[float], None]
            Closest value below the target. If the target is below the minimum
            value in the array, returns None.
        closest_upper : Union[NDArray[float], None]
            Closest value above the target. If the target is above the maximum
            value in the array, returns None.

    Examples
    --------
    Let's find the closest values above and below 5 in an array.

    >>> array = np.array([1,2,3,4,5,6,7,8,9,10])
    >>> closest(array, 5)
    (5, 6)
    """
    if not isinstance(array, np.ndarray):
        array = np.ndarray(array)

    if isinstance(array, np.ndarray):
        exact_value = array[array == target]

        if exact_value.size > 0:
            return exact_value[0], exact_value[0]

        younger_ages = array[array < target]
        older_ages = array[array > target]

        if younger_ages.size == 0:
            closest_lower = None
        else:
            closest_lower = younger_ages[np.argmin(np.abs(younger_ages - target))]

        if older_ages.size == 0:
            closest_upper = None
        else:
            closest_upper = older_ages[np.argmin(np.abs(older_ages - target))]

        return closest_lower, closest_upper
    raise ValueError("Cannot Cast to numpy array!")


def interpolate_arrays(
    array_lower: npt.NDArray,
    array_upper: npt.NDArray,
    target: float,
    lower: float,
    upper: float,
    joinCol: Union[int, None] = None,
) -> npt.NDArray:
    """
    Interpolate between two arrays. The arrays must have the same shape.

    Parameters
    ----------
        array_lower : NDArray[float]
            Lower bounding array.
        array_upper : NDArray[float]
            Upper bounding array.
        target : float
            Target value to interpolate to.
        lower : float
            value at lower bounding array
        upper : float
            value at upper bounding array
        joinCol : int, default=None
            Column to join on. If None, assumes the arrays are parallel
    Returns
    -------
        interpolated_array : NDArray[float]
            Interpolated array at target value.

    Examples
    --------
    Let's interpolate between two arrays.

    >>> array_lower = np.array([1,2,3,4,5,6,7,8,9,10])
    >>> array_upper = np.array([11,12,13,14,15,16,17,18,19,20])

    >>> interpolate_arrays(array_lower, array_upper, 5.5, 5, 6)
    """
    if array_lower is None or array_upper is None:
        raise ValueError("Both arrays must be non-None")

    if not isinstance(array_lower, np.ndarray):
        array_lower = np.array(array_lower)

    if not isinstance(array_upper, np.ndarray):
        array_upper = np.array(array_upper)

    if joinCol is not None:
        shared = np.intersect1d(array_lower[:, joinCol], array_upper[:, joinCol])
        lowerMask = np.isin(array_lower[:, joinCol], shared)
        upperMask = np.isin(array_upper[:, joinCol], shared)
        array_lower = array_lower[lowerMask]
        array_upper = array_upper[upperMask]
    # Ensure both arrays have the same shape
    assert array_lower.shape == array_upper.shape, "Arrays must have the same shape"

    # Calculate the interpolation weights
    lower_weight = (upper - target) / (upper - lower)
    upper_weight = (target - lower) / (upper - lower)

    # Perform element-wise interpolation
    interpolated_array = (array_lower * lower_weight) + (array_upper * upper_weight)

    return interpolated_array


def interpolate_keyed_arrays(
    arr1: Sequence,
    arr2: Sequence,
    target: float,
    lower: float,
    upper: float,
    key: int = 0,
) -> Sequence:
    # Ensure arrays are numpy arrays
    arr1 = np.array(arr1)
    arr2 = np.array(arr2)

    # Extract the EEP values from both arrays
    eep_arr1 = arr1[:, key]
    eep_arr2 = arr2[:, key]

    # Find the intersection of the EEP values in both arrays
    common_eeps = np.intersect1d(eep_arr1, eep_arr2)

    # Filter the arrays to keep only rows with common EEP values
    arr1_filtered = arr1[np.isin(eep_arr1, common_eeps)]
    arr2_filtered = arr2[np.isin(eep_arr2, common_eeps)]

    # Sort the filtered arrays by EEP values
    arr1_filtered = arr1_filtered[np.argsort(arr1_filtered[:, 0])]
    arr2_filtered = arr2_filtered[np.argsort(arr2_filtered[:, 0])]

    # Perform the linear interpolation element-wise
    interp_ratio = (target - lower) / (upper - lower)
    interpolated_arr = arr1_filtered + interp_ratio * (arr2_filtered - arr1_filtered)

    return interpolated_arr


def get_logger(
    name,
    fileName="fidanka.log",
    level=logging.INFO,
    flevel=logging.INFO,
    clevel=logging.WARNING,
):
    # logger = logging.getLogger(name)
    # logger.setLevel(level)

    # if not logger.hasHandlers():
    #     # create a file handler
    #     file_handler = logging.FileHandler(fileName)
    #     file_handler.setLevel(flevel)

    #     console_handler = logging.StreamHandler()
    #     console_handler.setLevel(clevel)

    #     formatter = logging.Formatter(
    #         "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    #     )
    #     file_handler.setFormatter(formatter)
    #     console_handler.setFormatter(formatter)

    #     logger.addHandler(file_handler)
    #     logger.addHandler(console_handler)

    logger = LoggerManager.get_logger()
    return logger


def pfD(r, I):
    """
    Return a function which givex the perpendicular distance between a point and
    a function evaluated at some point x

    Parameters
    ----------
        r : np.ndarray[float64]
            2-vector (x,y), some point
        I : Callable
            Function of a single parameter I(x) -> y.

    Returns
    -------
        d : Callable
            Function of form d(x) which gives the distance between r and I(x)
    """
    return lambda m: np.sqrt((m - r[0]) ** 2 + (I(m) - r[1]) ** 2)


def measusre_perpendicular_distance(f1, f2, domain, pbar=False):
    """
    Measure the perpendicular distance between two functions
    over a given domain.

    Parameters
    ----------
        f1 : Callable
            Function of a single parameter f1(x) -> y.
        f2 : Callable
            Function of a single parameter f2(x) -> y.
        domain : np.ndarray[float64]
            Domain over which to measure the distance.
        pbar : bool, default=False
            Show progress bar.

    Returns
    -------
        minDist : np.ndarray[float64]
            Minimum distance between the two functions over the domain.

    Examples
    --------
    Let's measure the perpendicular distance between two functions.

    >>> f1 = lambda x: x**2
    >>> f2 = lambda x: x**3
    >>> domain = np.linspace(0, 1, 100)
    >>> minDist = measusre_perpendicular_distance(f1, f2, domain)

    """
    minDist = np.zeros(len(domain))
    for idx, x in tqdm(enumerate(domain), disable=not pbar):
        r0 = np.array([x, f1(x)])
        r1 = np.array([x, f2(x)])
        approxDist = np.sqrt((r0[0] - r1[0]) ** 2 + (r0[1] - r1[1]) ** 2)
        d = pfD(r0, f2)
        nearestPoint = minimize(d, x0=approxDist, method="Nelder-Mead")
        if not nearestPoint.success:
            print("Perpendicular Minimization Failed. No local Minima Identified.")
        else:
            minDist[idx] = d(nearestPoint.x[0])
    return minDist


if __name__ == "__main__":
    f1 = lambda x: np.cos(x)
    f2 = lambda x: np.sin(x)
    domain = np.linspace(-2 * np.pi, 2 * np.pi, 100)
    minDist = measusre_perpendicular_distance(f1, f2, domain)

    # plt.plot(domain, f1(domain))
    # plt.plot(domain, f2(domain))
    # plt.xlim(-2*np.pi, 2*np.pi)
    # plt.ylim(-2*np.pi, 2*np.pi)
    # plt.ylim(-6.5, -5)
    # plt.plot(domain, minDist)
    # plt.show()
