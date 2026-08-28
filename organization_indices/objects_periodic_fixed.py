import numpy as np
import skimage.measure as skm
import shapely.geometry as spg
from scipy import ndimage


def wrap_distance(coord1, coord2, domain_length):
    """Calculate the periodic distance between coordinates, handling wrap-around."""
    return np.minimum(np.abs(coord1 - coord2), domain_length - np.abs(coord1 - coord2))


def stitch_periodic_boundaries(image):
    """
    Stitch objects that wrap around periodic boundaries by padding and re-labeling.
    This ensures objects split across domain edges are treated as single objects.
    
    Parameters:
    -----------
    image : np.ndarray
        Binary image (2D array) with 1s for objects and 0s for background
        
    Returns:
    --------
    labeled : np.ndarray
        Labeled image with periodic boundary conditions properly handled
    shift_y : int
        Vertical shift applied (for coordinate adjustment)
    shift_x : int
        Horizontal shift applied (for coordinate adjustment)
    """
    ny, nx = image.shape
    
    # Create a padded image: replicate edges to allow wrapping detection
    # Pad with half the domain size to ensure objects can be connected
    pad_size_y = ny // 4
    pad_size_x = nx // 4
    
    # Pad by wrapping (periodic boundary conditions)
    padded = np.pad(image, ((pad_size_y, pad_size_y), (pad_size_x, pad_size_x)), mode='wrap')
    
    # Label the padded image
    labeled_padded = skm.label(padded, background=0, connectivity=2)
    
    # Extract the central region (original domain size)
    labeled = labeled_padded[pad_size_y:pad_size_y+ny, pad_size_x:pad_size_x+nx]
    
    return labeled, pad_size_y, pad_size_x


#######################################################################################
################### class containing all the regions and polynoms #####################
#######################################################################################

class make_objects :

    def __init__(self, image):
        "Create the regions and polynoms with periodic boundary handling"

        # Fill holes first
        image = ndimage.binary_fill_holes(image).astype(int)
        
        # Use periodic boundary-aware labeling
        labeled, shift_y, shift_x = stitch_periodic_boundaries(image)
        regions = skm.regionprops(labeled)

        perimeter_ = []
        polynoms = []
        for r in regions:
            bounds = r.bbox
            y_length = bounds[2] - bounds[0]
            x_length = bounds[3] - bounds[1]
            # prepare bed to put layout in
            bed = np.zeros(shape=(y_length + 2, x_length + 2))
            bed[1:-1, 1:-1] = r.image.astype(int)
            # get the contour needed for shapely
            contour = skm.find_contours(bed, level=0.5, fully_connected='high')
            # increase coordinates to get placement inside of original input array right
            contour[0][:, 0] += bounds[0]  # increase y-values
            contour[0][:, 1] += bounds[1]  # increase x-values

            m_poly = spg.Polygon(contour[0])
            polynoms.append(m_poly)

            # compute the perimeter
            negative_bed = np.where(bed==0, 1, 0)
            perimeter_.append( np.sum(bed[:-1,:]*negative_bed[1: ,:]) +
                               np.sum(bed[ 1:,:]*negative_bed[:-1,:]) +
                               np.sum(bed[:,:-1]*negative_bed[:,1: ]) +
                               np.sum(bed[:,1: ]*negative_bed[:,:-1])
                               )


        self.labeled  = labeled
        self.regions  = regions
        self.polynoms = polynoms

        self.area_skm  =   np.sum([r.area     for r in self.regions ])
        self.area_spg  =   np.sum([p.area+0.5 for p in self.polynoms]) # +0.5 is needed because of the shape of spg.Polygon
        self.areas     = np.array([r.area     for r in self.regions])  # I will use these in the metrics
        self.centroids = np.array([r.centroid for r in self.regions])
        self.diameters = np.array([r.equivalent_diameter     for r in self.regions])
        #self.perimeters= np.array([p.length for p in self.polynoms]) # +0.5 is needed because of the shape of spg.Polygon
        self.perimeter = np.array(perimeter_)

        self.number_of_objects = len(self.polynoms)


#######################################################################################
############### class containing the list of all the pairs of objects #################
#######################################################################################

class make_pairs:

    def __init__(self, objects, domain_length_x, domain_length_y):
        self.objects = objects
        self.number_of_objects      = objects.number_of_objects
        self.number_of_combinations = objects.number_of_objects * (objects.number_of_objects-1) / 2


        self.compute_distance_centroids (domain_length_x, domain_length_y)
        self.compute_distance_edges (domain_length_x, domain_length_y)




    def compute_distance_centroids (self, domain_length_x, domain_length_y) :
        centroids = self.objects.centroids
        xs  = np.array([c[1] for c in centroids])  # c[1] is X (column)
        ys  = np.array([c[0] for c in centroids])  # c[0] is Y (row)

        # Compute the periodic distances
        dist_x = wrap_distance(xs[:, None], xs[None, :], domain_length_x)
        dist_y = wrap_distance(ys[:, None], ys[None, :], domain_length_y)
        distances =  np.sqrt(dist_x**2 + dist_y**2)
        np.fill_diagonal(distances, np.nan)  # it is inplace

        self.centroids_x          = xs
        self.centroids_y          = ys
        self.distance_centroids_x = dist_x
        self.distance_centroids_y = dist_y
        self.distance_centroids   = distances

        # compute the nearest neighbour distance
        self.dist_min = np.nanmin(distances, axis=0) if self.number_of_objects > 1 else np.nan


    def compute_distance_edges (self, domain_length_x, domain_length_y) :
        """
        Compute minimum distance between object edges with periodic boundaries.
        FIXED: Corrected coordinate ordering (Y=rows, X=columns).
        """
        n_objects = self.number_of_objects
        distance_edges = np.empty((self.number_of_objects, self.number_of_objects))

        for n in range(n_objects):
            poly_n = self.objects.polynoms[n]
            coords_n = np.array(poly_n.exterior.coords)

            for m in range(n+1, n_objects):
                poly_m = self.objects.polynoms[m]
                coords_m = np.array(poly_m.exterior.coords)

                min_dist = np.inf
                for coord1 in coords_n:
                    # FIXED: coord1[0] is Y (row), coord1[1] is X (column)
                    # Use domain_length_y for Y distances, domain_length_x for X distances
                    dists = np.sqrt(
                        wrap_distance(coord1[0], coords_m[:, 0], domain_length_y)**2 +
                        wrap_distance(coord1[1], coords_m[:, 1], domain_length_x)**2
                    )
                    min_dist = min(min_dist, np.min(dists))

                distance_edges[n, m] = min_dist
                distance_edges[m, n] = min_dist  # Ensure symmetry

        np.fill_diagonal(distance_edges, np.nan)
        self.distance_edges =  distance_edges
