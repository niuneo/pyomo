try:
    import numpy as np
    import pandas as pd
    from scipy import stats
    import itertools
    from scipy.interpolate import griddata
    import seaborn as sns
    import matplotlib.pyplot as plt
    import matplotlib.tri as tri
    from matplotlib.lines import Line2D
    imports_available = True
except ImportError:
    imports_available = False


def _get_variables(ax,columns):
    sps = ax.get_subplotspec()
    nx = sps.get_geometry()[1]
    ny = sps.get_geometry()[0]
    cell = sps.get_geometry()[2]
    xloc = int(np.mod(cell,nx))
    yloc = int(np.mod((cell-xloc)/nx, ny))

    xvar = columns[xloc]
    yvar = columns[yloc]
    #print(sps.get_geometry(), cell, xloc, yloc, xvar, yvar)
    
    return xvar, yvar, (xloc, yloc)


def _get_XYgrid(x,y,ncells):
    xlin = np.linspace(min(x)-abs(max(x)-min(x))/2, max(x)+abs(max(x)-min(x))/2, ncells)
    ylin = np.linspace(min(y)-abs(max(y)-min(y))/2, max(y)+abs(max(y)-min(y))/2, ncells)
    X, Y = np.meshgrid(xlin, ylin)
    
    return X,Y


def _get_data_slice(xvar,yvar,columns,data,theta_star):

    search_ranges = {} 
    for var in columns:
        if var in [xvar,yvar]:
            search_ranges[var] = data[var].unique()
        else:
            search_ranges[var] = [theta_star[var]]

    data_slice = pd.DataFrame(list(itertools.product(*search_ranges.values())),
                            columns=search_ranges.keys())
    
    # griddata will not work with linear interpolation if the data 
    # values are constant in any dimension
    for col in data[columns].columns:
        cv = data[col].std()/data[col].mean() # Coefficient of variation
        if cv < 1e-8: 
            temp = data.copy()
            # Add variation (the interpolation is later scaled)
            if cv == 0:
                temp[col] = temp[col] + data[col].mean()/10
            else:
                temp[col] = temp[col] + data[col].std()
            data = data.append(temp, ignore_index=True)
    
    data_slice['obj'] = griddata(np.array(data[columns]),
                             np.array(data[['obj']]),
                             np.array(data_slice[columns]),
                             method='linear',
                             rescale=True)
        
    X = data_slice[xvar]
    Y = data_slice[yvar]
    Z = data_slice['obj']
    
    return X,Y,Z
    

def _add_scatter(x,y,color,label,columns,theta_star):
    ax = plt.gca()
    xvar, yvar, loc = _get_variables(ax, columns)
    
    ax.scatter(theta_star[xvar], theta_star[yvar], c=color, s=35)
    
    
def _add_rectangle_CI(x,y,color,label,columns,lower_bound,upper_bound):
    ax = plt.gca()
    xvar, yvar, loc = _get_variables(ax,columns)

    xmin = lower_bound[xvar]
    ymin = lower_bound[yvar]
    xmax = upper_bound[xvar]
    ymax = upper_bound[yvar]
    
    ax.plot([xmin, xmax], [ymin, ymin], color=color)
    ax.plot([xmax, xmax], [ymin, ymax], color=color)
    ax.plot([xmax, xmin], [ymax, ymax], color=color)
    ax.plot([xmin, xmin], [ymax, ymin], color=color)


def _add_scipy_dist_CI(x,y,color,label,columns,ncells,alpha,dist,theta_star):
    ax = plt.gca()
    xvar, yvar, loc = _get_variables(ax,columns)
    
    X,Y = _get_XYgrid(x,y,ncells)
    
    data_slice = []
    
    if isinstance(dist, stats._multivariate.multivariate_normal_frozen):
        for var in theta_star.index:
            if var == xvar:
                data_slice.append(X)
            elif var == yvar:
                data_slice.append(Y)
            elif var not in [xvar,yvar]:
                data_slice.append(np.array([[theta_star[var]]*ncells]*ncells))
        data_slice = np.dstack(tuple(data_slice))
        
    elif isinstance(dist, stats.kde.gaussian_kde):
        for var in theta_star.index:
            if var == xvar:
                data_slice.append(X.ravel())
            elif var == yvar:
                data_slice.append(Y.ravel())
            elif var not in [xvar,yvar]:
                data_slice.append(np.array([theta_star[var]]*ncells*ncells))
        data_slice = np.array(data_slice)
    else:
        return
        
    Z = dist.pdf(data_slice)
    Z = Z.reshape((ncells, ncells))
    
    ax.contour(X,Y,Z, levels=[alpha], colors=color) 
    
    
def _add_obj_contour(x,y,color,label,columns,data,theta_star):
    ax = plt.gca()
    xvar, yvar, loc = _get_variables(ax,columns)

    try:
        X, Y, Z = _get_data_slice(xvar,yvar,columns,data,theta_star)
        
        triang = tri.Triangulation(X, Y)
        cmap = plt.cm.get_cmap('Greys')
        
        plt.tricontourf(triang,Z,cmap=cmap)
    except:
        print('Objective contour plot for', xvar, yvar,'slice failed')
    
    
def _add_LR_contour(x,y,color,label,columns,data,theta_star,threshold):
    ax = plt.gca()
    xvar, yvar, loc = _get_variables(ax,columns)
    
    X, Y, Z = _get_data_slice(xvar,yvar,columns,data,theta_star)
    
    triang = tri.Triangulation(X, Y)
    
    plt.tricontour(triang,Z,[threshold], colors='r')


def _set_axis_limits(g, axis_limits, theta_vals, theta_star):
    
    if theta_star is not None:
        theta_vals = theta_vals.append(theta_star, ignore_index=True)
        
    if axis_limits is None:
        axis_limits = {}
        for col in theta_vals.columns:
            theta_range = np.abs(theta_vals[col].max() - theta_vals[col].min())
            if theta_range < 1e-10:
                theta_range  = theta_vals[col].max()/10
            axis_limits[col] = [theta_vals[col].min() - theta_range/4, 
                                theta_vals[col].max() + theta_range/4]
    for ax in g.fig.get_axes():
        xvar, yvar, (xloc, yloc) = _get_variables(ax,theta_vals.columns)
        if xloc != yloc: # not on diagonal
            ax.set_ylim(axis_limits[yvar])
            ax.set_xlim(axis_limits[xvar])
        else: # on diagonal
            ax.set_xlim(axis_limits[xvar])

            
def pairwise_plot(theta_values, theta_star=None, alpha=None, distributions=[], 
                  axis_limits=None, title=None, add_obj_contour=True, 
                  add_legend=True, filename=None):
    """
    Plot pairwise relationship for theta values, and optionally confidence 
    intervals and results from likelihood ratio tests
    
    Parameters
    ----------
    theta_values: DataFrame, columns = variable names and (optionally) 'obj' and alpha values
        Theta values and (optionally) an objective value and results from 
        leaveNout_bootstrap_analysis, likelihood_ratio_test, or 
        confidence_region_test
    theta_star: dict, keys = variable names, optional
        Theta* (or other individual values of theta, also used to 
        slice higher dimensional contour intervals in 2D)
    alpha: float, optional
        Confidence interval value, if an alpha value is given and the 
        distributions list is empty, the data will be filtered by True/False 
        values using the column name whos value equals alpha (see results from
        leaveNout_bootstrap_analysis, likelihood_ratio_test, or 
        confidence_region_test)
    distributions: list of strings, optional
        Statistical distribution used used to define a confidence region, 
        options = 'MVN' for multivariate_normal, 'KDE' for gaussian_kde, and 
        'Rect' for rectangular.
		Confidence interval is a 2D slice, using linear interpolation at theta*.
    axis_limits: dict, optional
        Axis limits in the format {variable: [min, max]}
    title: string, optional
        Plot title
    add_obj_contour: bool, optional
        Add a contour plot using the column 'obj' in theta_values.
        Contour plot is a 2D slice, using linear interpolation at theta*.
    add_legend: bool, optional
        Add a legend to the plot
    filename: string, optional
        Filename used to save the figure
    """

    if len(theta_values) == 0:
        return('Empty data')    
    if isinstance(theta_star, dict):
        theta_star = pd.Series(theta_star)
    if isinstance(theta_star, pd.DataFrame):
        theta_star = theta_star.loc[0,:]
    
    theta_names = [col for col in theta_values.columns if (col not in ['obj']) 
                        and (not isinstance(col, float)) and (not isinstance(col, int))]
    
    # Filter data by alpha
    if (alpha in theta_values.columns) and (len(distributions) == 0):
        thetas = theta_values.loc[theta_values[alpha] == True, theta_names]
    else:
        thetas = theta_values[theta_names]
    
    if theta_star is not None:
        theta_star = theta_star[theta_names]
    
    legend_elements = []
    
    g = sns.PairGrid(thetas)
    
    # Plot histogram on the diagonal
    g.map_diag(sns.distplot, kde=False, hist=True, norm_hist=False) 
    
    # Plot filled contours using all theta values based on obj
    if 'obj' in theta_values.columns and add_obj_contour:
        g.map_offdiag(_add_obj_contour, columns=theta_names, data=theta_values, 
                      theta_star=theta_star)
        
    # Plot thetas
    g.map_offdiag(plt.scatter, s=10)
    legend_elements.append(Line2D([0], [0], marker='o', color='w', label='thetas',
                          markerfacecolor='cadetblue', markersize=5))
    
    # Plot theta*
    if theta_star is not None:
        g.map_offdiag(_add_scatter, color='k', columns=theta_names, theta_star=theta_star)
        
        legend_elements.append(Line2D([0], [0], marker='o', color='w', label='theta*',
                                      markerfacecolor='k', markersize=6))
    
    # Plot confidence regions
    colors = ['r', 'mediumblue', 'darkgray']
    if (alpha is not None) and (len(distributions) > 0):
        
        if theta_star is None:
            print("""theta_star is not defined, confidence region slice will be 
                  plotted at the mean value of theta""")
            theta_star = thetas.mean()
        
        mvn_dist = None
        kde_dist = None
        for i, dist in enumerate(distributions):
            if dist == 'Rect':
                lb, ub = fit_rect_dist(thetas, alpha)
                g.map_offdiag(_add_rectangle_CI, color=colors[i], columns=theta_names, 
                            lower_bound=lb, upper_bound=ub)
                legend_elements.append(Line2D([0], [0], color=colors[i], lw=1, label=dist))
                
            elif dist == 'MVN':
                mvn_dist = fit_mvn_dist(thetas, alpha)
                Z = mvn_dist.pdf(thetas)
                score = stats.scoreatpercentile(Z, (1-alpha)*100) 
                g.map_offdiag(_add_scipy_dist_CI, color=colors[i], columns=theta_names, 
                            ncells=100, alpha=score, dist=mvn_dist, 
                            theta_star=theta_star)
                legend_elements.append(Line2D([0], [0], color=colors[i], lw=1, label=dist))
                
            elif dist == 'KDE':
                kde_dist = fit_kde_dist(thetas, alpha)
                Z = kde_dist.pdf(thetas.transpose())
                score = stats.scoreatpercentile(Z, (1-alpha)*100) 
                g.map_offdiag(_add_scipy_dist_CI, color=colors[i], columns=theta_names, 
                            ncells=100, alpha=score, dist=kde_dist, 
                            theta_star=theta_star)
                legend_elements.append(Line2D([0], [0], color=colors[i], lw=1, label=dist))
            
            else:
                print('Invalid distribution')
            
    _set_axis_limits(g, axis_limits, thetas, theta_star)
    
    for ax in g.axes.flatten():
        ax.ticklabel_format(style='sci', scilimits=(-2,2), axis='both')
        
        if add_legend:
            xvar, yvar, loc = _get_variables(ax, theta_names)
            if loc == (len(theta_names)-1,0):
                ax.legend(handles=legend_elements, loc='best', prop={'size': 8})
    if title:
        g.fig.subplots_adjust(top=0.9)
        g.fig.suptitle(title) 
        
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        plt.close()
    
    # Work in progress
    # Plot lower triangle graphics in separate figures, useful for presentations
    lower_triangle_only = False
    if lower_triangle_only:
        for ax in g.axes.flatten():
            xvar, yvar, (xloc, yloc) = _get_variables(ax, theta_names)
            if xloc < yloc: # lower triangle
                ax.remove()
                
                ax.set_xlabel(xvar)
                ax.set_ylabel(yvar)
                
                fig = plt.figure()
                ax.figure=fig
                fig.axes.append(ax)
                fig.add_axes(ax)
                
                f, dummy = plt.subplots()
                bbox = dummy.get_position()
                ax.set_position(bbox) 
                dummy.remove()
                plt.close(f)

                ax.tick_params(reset=True)
                
                if add_legend:
                    ax.legend(handles=legend_elements, loc='best', prop={'size': 8})
                
        plt.close(g.fig)
    
    plt.show()
    

def fit_rect_dist(theta_values, alpha):
    """
    Fit a rectangular distribution to theta values
    
    Parameters
    ----------
    theta_values: DataFrame, columns = variable names
        Theta values
    alpha: float, optional
        Confidence interval value
    
    Returns
    ---------
    tuple containing lower bound and upper bound for each variable
    """
    tval = stats.t.ppf(1-(1-alpha)/2, len(theta_values)-1) # Two-tail
    m = theta_values.mean()
    s = theta_values.std()
    lower_bound = m-tval*s
    upper_bound = m+tval*s
    
    return lower_bound, upper_bound
    
def fit_mvn_dist(theta_values, alpha):
    """
    Fit a multivariate normal distribution to theta values
    
    Parameters
    ----------
    theta_values: DataFrame, columns = variable names
        Theta values
    alpha: float, optional
        Confidence interval value
    
    Returns
    ---------
    scipy.stats.multivariate_normal distribution
    """
    dist = stats.multivariate_normal(theta_values.mean(), 
                                    theta_values.cov(), allow_singular=True)
    return dist

def fit_kde_dist(theta_values, alpha):
    """
    Fit a gaussian kernel-density estimate to theta values
    
    Parameters
    ----------
    theta_values: DataFrame, columns = variable names
        Theta values
    alpha: float, optional
        Confidence interval value
    
    Returns
    ---------
    scipy.stats.gaussian_kde distribution
    """
    dist = stats.gaussian_kde(theta_values.transpose().values)
    
    return dist
